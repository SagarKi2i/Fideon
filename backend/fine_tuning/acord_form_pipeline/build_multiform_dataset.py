from __future__ import annotations

import argparse
import json
import logging
import random
import re
from collections import defaultdict
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .clean_ocr import clean_ocr_text
from .schema_registry import SCHEMA_REGISTRY, normalize_by_form

logger = logging.getLogger("acord.multiform.dataset")


def _system_prompt() -> str:
    return (
        "You are a strict ACORD document extractor.\n"
        "Rules:\n"
        "- Output ONLY valid JSON\n"
        "- Do NOT infer missing values\n"
        "- Use null for missing values\n"
        "- Include all schema keys"
    )


def _user_prompt(form_type: str, schema: List[str], text: str) -> str:
    return (
        f"[FORM={form_type.upper()}]\n\n"
        "FIELDS:\n"
        f"{schema}\n\n"
        "RULES:\n"
        "- Copy exact values only\n"
        "- No inference\n"
        "- Return strict JSON\n\n"
        "DOCUMENT:\n"
        f"{text}"
    )


def validate_sample(sample: Dict[str, Any]) -> bool:
    try:
        parsed = json.loads(sample["messages"][2]["content"])
        if not isinstance(parsed, dict):
            return False
        schema = SCHEMA_REGISTRY[sample["form_type"]]
        return all(k in parsed for k in schema)
    except Exception:
        return False


def _inject_noise(text: str) -> str:
    noisy = re.sub(r"\s+", " ", text)
    noisy = noisy.replace("Policy", "Po1icy").replace("Carrier", "Carrler")
    return noisy + "\n### random noise ###"


def _mask_nulls(text: str, labels: Dict[str, Any], schema: List[str]) -> Dict[str, Any]:
    out = dict(labels)
    k = random.sample(schema, k=max(1, min(2, len(schema))))
    for key in k:
        val = out.get(key)
        if val is not None:
            text = re.sub(re.escape(str(val)), "", text, flags=re.IGNORECASE)
        out[key] = None
    return {"text": text, "labels": out}


def _add_hard_negative(form_type: str, text: str, labels: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(labels)
    if "carrier" in SCHEMA_REGISTRY.get(form_type, []):
        text = f"{text}\nCarrier: ABC Insurance\nAgency: XYZ Services"
        out["carrier"] = "ABC Insurance"
    if "agency_name" in SCHEMA_REGISTRY.get(form_type, []):
        out["agency_name"] = None
    return {"text": text, "labels": out}


def _add_checkbox_table_sample(form_type: str, text: str, labels: Dict[str, Any]) -> Dict[str, Any]:
    if "lines_of_business" not in SCHEMA_REGISTRY.get(form_type, []):
        return {"text": text, "labels": labels}
    lob = ["Business Auto", "Commercial Property"]
    block = (
        "LINES OF BUSINESS:\n"
        "[X] Business Auto\n"
        "[X] Commercial Property\n"
        "[ ] Crime\n"
    )
    out = dict(labels)
    out["lines_of_business"] = ", ".join(lob)
    return {"text": f"{text}\n{block}", "labels": out}


def _make_sample(
    form_type: str,
    text: str,
    labels: Dict[str, Any],
    data_source: str = "real_ocr_llm_corrected",
) -> Dict[str, Any]:
    schema = SCHEMA_REGISTRY[form_type]
    return {
        "form_type": form_type,
        "data_source": data_source,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(form_type, schema, text)},
            {"role": "assistant", "content": json.dumps(labels, ensure_ascii=False)},
        ],
    }


def balance_dataset(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in samples:
        grouped[s["form_type"]].append(s)
    if not grouped:
        return []
    min_count = min(len(v) for v in grouped.values())
    balanced: List[Dict[str, Any]] = []
    for k in sorted(grouped.keys()):
        balanced.extend(grouped[k][:min_count])
    return balanced


def check_distribution(samples: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter([s.get("form_type", "unknown") for s in samples])
    logger.info("dataset_distribution=%s", dict(counts))
    return dict(counts)


def build_multiform_dataset(
    input_manifest: Path,
    ocr_text_dir: Path,
    out_jsonl: Path,
    missing_ratio: float = 0.30,
    noise_ratio: float = 0.20,
    hard_negative_ratio: float = 0.20,
    checkbox_ratio: float = 0.20,
    balance: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    random.seed(seed)
    rows = json.loads(input_manifest.read_text(encoding="utf-8"))
    samples: List[Dict[str, Any]] = []
    per_form = defaultdict(int)
    invalid = 0

    for row in rows:
        source = str(row.get("data_source", "real")).strip().lower()
        if source in {"synthetic", "synth", "generated", "fake"}:
            raise ValueError(
                f"Synthetic source is not allowed: file={row.get('file')} data_source={source}"
            )
        form_type = str(row.get("form_type", "")).strip().lower()
        if form_type not in SCHEMA_REGISTRY:
            logger.warning("Skipping unknown form_type=%s for file=%s", form_type, row.get("file"))
            continue
        text_file = ocr_text_dir / str(row["file"])
        raw = text_file.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_ocr_text(raw)
        labels = normalize_by_form(form_type, row.get("labels", {}))
        sample_source = str(row.get("data_source", "real_ocr_llm_corrected")).strip() or "real_ocr_llm_corrected"

        base = _make_sample(form_type, cleaned, labels, data_source=sample_source)
        samples.append(base)
        per_form[form_type] += 1

        if random.random() < missing_ratio:
            masked = _mask_nulls(cleaned, labels, SCHEMA_REGISTRY[form_type])
            samples.append(_make_sample(form_type, masked["text"], masked["labels"], data_source=sample_source))
            per_form[form_type] += 1
        if random.random() < noise_ratio:
            samples.append(_make_sample(form_type, _inject_noise(cleaned), labels, data_source=sample_source))
            per_form[form_type] += 1
        if random.random() < hard_negative_ratio:
            h = _add_hard_negative(form_type, cleaned, labels)
            samples.append(_make_sample(form_type, h["text"], h["labels"], data_source=sample_source))
            per_form[form_type] += 1
        if random.random() < checkbox_ratio:
            c = _add_checkbox_table_sample(form_type, cleaned, labels)
            samples.append(_make_sample(form_type, c["text"], c["labels"], data_source=sample_source))
            per_form[form_type] += 1

    if balance:
        samples = balance_dataset(samples)
    check_distribution(samples)

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for s in samples:
            if not validate_sample(s):
                invalid += 1
                continue
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    summary = {
        "total_samples": len(samples),
        "invalid_removed": invalid,
        "written": len(samples) - invalid,
        "samples_per_form": dict(per_form),
        "balanced": balance,
    }
    logger.info("multiform build summary=%s", summary)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    p = argparse.ArgumentParser(description="Build multi-form ACORD training dataset.")
    p.add_argument("--input-manifest", required=True)
    p.add_argument("--ocr-text-dir", required=True)
    p.add_argument("--out", default="acord_multiform_dataset.jsonl")
    p.add_argument("--missing-ratio", type=float, default=0.30)
    p.add_argument("--noise-ratio", type=float, default=0.20)
    p.add_argument("--hard-negative-ratio", type=float, default=0.20)
    p.add_argument("--checkbox-ratio", type=float, default=0.20)
    p.add_argument("--no-balance", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    out = build_multiform_dataset(
        input_manifest=Path(args.input_manifest),
        ocr_text_dir=Path(args.ocr_text_dir),
        out_jsonl=Path(args.out),
        missing_ratio=args.missing_ratio,
        noise_ratio=args.noise_ratio,
        hard_negative_ratio=args.hard_negative_ratio,
        checkbox_ratio=args.checkbox_ratio,
        balance=not args.no_balance,
        seed=args.seed,
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

