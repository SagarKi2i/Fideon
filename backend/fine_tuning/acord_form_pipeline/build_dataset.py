from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .clean_ocr import clean_ocr_text
from .schema import FIXED_SCHEMA_KEYS, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, normalize_label

logger = logging.getLogger("acord125.dataset_builder")


def validate_json(sample: Dict[str, Any]) -> bool:
    try:
        msgs = sample["messages"]
        if not isinstance(msgs, list) or len(msgs) != 3:
            return False
        assistant = msgs[2]["content"]
        parsed = json.loads(assistant)
        if not isinstance(parsed, dict):
            return False
        user_content = str(msgs[1].get("content", ""))
        if "Extract ONLY" in user_content:
            # Field-wise sample: exactly one task field expected.
            non_evidence = [k for k in parsed.keys() if not k.endswith("_evidence")]
            return len(non_evidence) == 1
        return all(k in parsed for k in FIXED_SCHEMA_KEYS)
    except Exception:
        return False


def _inject_noise(text: str) -> str:
    noisy = text
    noisy = re.sub(r"\s+", " ", noisy)
    # Simulate OCR confusion
    noisy = noisy.replace("Policy", "Po1icy").replace("Carrier", "Carrler").replace("Phone", "Ph0ne")
    # Random line breaks
    noisy = noisy.replace(", ", ",\n", 2)
    return noisy


def _augment_sample(text: str) -> List[str]:
    variants: List[str] = []
    # Remove optional lines to simulate partial OCR coverage.
    variants.append(re.sub(r"(?im)^.*email:.*$\n?", "", text))
    # Shuffle lines for ordering variation.
    lines = [ln for ln in text.split("\n") if ln.strip()]
    random.shuffle(lines)
    variants.append("\n".join(lines))
    # Add random noise.
    variants.append(text + "\n### random noise ###")
    return variants


def validate_label_vs_text(labels: Dict[str, Any], text: str, row_id: str | None = None) -> int:
    warnings = 0
    source = (text or "").lower()
    for key, value in labels.items():
        if value is None:
            continue
        token = str(value).strip().lower()
        if token and token not in source:
            warnings += 1
            logger.warning(
                "Possible label/text mismatch row=%s key=%s value=%s",
                row_id or "unknown",
                key,
                value,
            )
    return warnings


def _mask_fields(text: str, labels: Dict[str, Any], keys_to_mask: List[str]) -> Tuple[str, Dict[str, Any]]:
    updated = dict(labels)
    masked_text = text
    for key in keys_to_mask:
        val = labels.get(key)
        if val:
            masked_text = re.sub(re.escape(str(val)), "", masked_text, flags=re.IGNORECASE)
        updated[key] = None
    return masked_text, updated


def add_evidence(text: str, label: Dict[str, Any]) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    for key, value in label.items():
        if value is None:
            evidence[f"{key}_evidence"] = None
            continue
        m = re.search(re.escape(str(value)), text, flags=re.IGNORECASE)
        evidence[f"{key}_evidence"] = m.group(0) if m else None
    return evidence


def _assistant_payload(cleaned_text: str, labels: Dict[str, Any], with_evidence: bool = True) -> Dict[str, Any]:
    payload = normalize_label(labels)
    if with_evidence:
        payload.update(add_evidence(cleaned_text, payload))
    return payload


def _to_chat_sample(cleaned_text: str, labels: Dict[str, Any], with_evidence: bool = True) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(input_text=cleaned_text)},
            {"role": "assistant", "content": json.dumps(_assistant_payload(cleaned_text, labels, with_evidence=with_evidence), ensure_ascii=False)},
        ]
    }


def _to_fieldwise_samples(cleaned_text: str, labels: Dict[str, Any], include_evidence: bool = True) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    norm = normalize_label(labels)
    for key in FIXED_SCHEMA_KEYS:
        payload: Dict[str, Any] = {key: norm.get(key)}
        if include_evidence:
            ev = add_evidence(cleaned_text, norm)
            payload[f"{key}_evidence"] = ev.get(f"{key}_evidence")
        out.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"{USER_PROMPT_TEMPLATE.format(input_text=cleaned_text)}\n\nExtract ONLY {key}",
                    },
                    {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            }
        )
    return out


def _contrastive_negative_sample(cleaned_text: str, labels: Dict[str, Any]) -> Dict[str, Any]:
    # Deliberately confusing text where "Agent" should not overwrite "agency_name".
    contrastive_text = (
        f"{cleaned_text}\n"
        "Agent: XYZ Corp\n"
        "Carrier: ABC Insurance\n"
    )
    updated = dict(normalize_label(labels))
    updated["carrier"] = "ABC Insurance"
    # Explicitly force known confusion slot to null.
    updated["agency_name"] = None
    return _to_chat_sample(contrastive_text, updated, with_evidence=True)


def build_dataset(
    input_manifest: Path,
    ocr_text_dir: Path,
    out_jsonl: Path,
    missing_ratio: float = 0.30,
    noise_ratio: float = 0.20,
    fieldwise_ratio: float = 0.35,
    contrastive_ratio: float = 0.25,
    min_samples_target: int = 300,
    seed: int = 42,
) -> Dict[str, int]:
    """
    input_manifest format:
    [
      {
        "id": "doc-1",
        "text_file": "doc-1.txt",
        "labels": {
          "agency_name": "...", "contact_name": "...", "carrier": "...",
          "policy_number": "...", "email": "...", "phone": "..."
        }
      }
    ]
    """
    random.seed(seed)
    rows = json.loads(input_manifest.read_text(encoding="utf-8"))
    samples: List[Dict[str, Any]] = []
    invalid = 0
    label_warnings = 0

    for row in rows:
        text_file = ocr_text_dir / row["text_file"]
        raw = text_file.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_ocr_text(raw)
        labels = normalize_label(row.get("labels", {}))
        label_warnings += validate_label_vs_text(labels, cleaned, row_id=str(row.get("id", "")))

        # Base sample
        samples.append(_to_chat_sample(cleaned, labels, with_evidence=True))

        # 30% missing-field variants
        if random.random() < missing_ratio:
            k = random.sample(FIXED_SCHEMA_KEYS, k=random.randint(1, 2))
            masked_text, masked_labels = _mask_fields(cleaned, labels, k)
            samples.append(_to_chat_sample(masked_text, masked_labels, with_evidence=True))

        # 20% noisy OCR variants
        if random.random() < noise_ratio:
            noisy = _inject_noise(cleaned)
            samples.append(_to_chat_sample(noisy, labels, with_evidence=True))
            for aug in _augment_sample(noisy):
                samples.append(_to_chat_sample(aug, labels, with_evidence=True))

        if random.random() < contrastive_ratio:
            samples.append(_contrastive_negative_sample(cleaned, labels))

        if random.random() < fieldwise_ratio:
            samples.extend(_to_fieldwise_samples(cleaned, labels, include_evidence=True))

    # If still small, expand by deterministic augmentation passes.
    i = 0
    while len(samples) < min_samples_target and i < len(samples):
        base = samples[i]
        user_text = base["messages"][1]["content"].split("Document:\n", 1)[-1]
        ref = json.loads(base["messages"][2]["content"])
        for aug in _augment_sample(user_text):
            samples.append(_to_chat_sample(aug, ref, with_evidence=False))
            if len(samples) >= min_samples_target:
                break
        i += 1

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for s in samples:
            if not validate_json(s):
                invalid += 1
                continue
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    written = len(samples) - invalid
    logger.info(
        "Dataset build complete: total=%s invalid_removed=%s written=%s label_warnings=%s",
        len(samples),
        invalid,
        written,
        label_warnings,
    )
    return {
        "total_samples": len(samples),
        "invalid_removed": invalid,
        "written": written,
        "label_warnings": label_warnings,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description="Build ACORD 125 chat-format JSONL from raw OCR text.")
    parser.add_argument("--input-manifest", required=True, help="Path to labels manifest JSON")
    parser.add_argument("--ocr-text-dir", required=True, help="Directory containing raw OCR .txt files")
    parser.add_argument("--out", default="acord_dataset.jsonl")
    parser.add_argument("--missing-ratio", type=float, default=0.30)
    parser.add_argument("--noise-ratio", type=float, default=0.20)
    parser.add_argument("--fieldwise-ratio", type=float, default=0.35)
    parser.add_argument("--contrastive-ratio", type=float, default=0.25)
    parser.add_argument("--min-samples-target", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    stats = build_dataset(
        input_manifest=Path(args.input_manifest),
        ocr_text_dir=Path(args.ocr_text_dir),
        out_jsonl=Path(args.out),
        missing_ratio=args.missing_ratio,
        noise_ratio=args.noise_ratio,
        fieldwise_ratio=args.fieldwise_ratio,
        contrastive_ratio=args.contrastive_ratio,
        min_samples_target=args.min_samples_target,
        seed=args.seed,
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

