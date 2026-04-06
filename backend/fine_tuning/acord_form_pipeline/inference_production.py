from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from .postprocess import (
    compute_confidence,
    compute_field_confidence,
    compute_trust_score,
    consistency_check,
    apply_field_position_heuristics,
    enforce_grounding,
    enforce_schema,
    rule_based_extraction,
    validate_fields,
    validate_json,
    verify_field,
)
from .schema import FIXED_SCHEMA_KEYS, SYSTEM_PROMPT
from .schema_registry import SCHEMA_REGISTRY

_CACHE: Dict[str, Dict[str, Any]] = {}
_MODEL_CACHE: Dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()


def build_prompt(text: str, form_type: str = "acord_125", schema: Optional[List[str]] = None) -> str:
    schema_keys = schema or FIXED_SCHEMA_KEYS
    return (
        f"[FORM={form_type.upper()}]\n\n"
        "FIELDS:\n"
        f"{schema_keys}\n\n"
        "RULES:\n"
        "- Copy exact values only\n"
        "- No inference\n"
        "- Return strict JSON\n"
        "- If exact match not found -> null\n\n"
        "DOCUMENT:\n"
        f"{text}"
    )


def build_field_prompt(field: str, text: str, form_type: str = "acord_125") -> str:
    return (
        f"[FORM={form_type.upper()}]\n\n"
        f"Extract ONLY {field} from the document.\n\n"
        "RULES:\n"
        "- Copy EXACT text\n"
        "- If not found -> null\n"
        f'- Output JSON: {{"{field}": value}}\n'
        "- No extra text\n\n"
        "DOCUMENT:\n"
        f"{text}"
    )


def build_retry_prompt(text: str, form_type: str = "acord_125", schema: Optional[List[str]] = None) -> str:
    schema_keys = schema or FIXED_SCHEMA_KEYS
    return (
        f"[FORM={form_type.upper()}]\n\n"
        "FIELDS:\n"
        f"{schema_keys}\n\n"
        "RULES:\n"
        "- Be stricter. Copy values EXACTLY from text\n"
        "- If uncertain, return null\n"
        "- No inference\n"
        "- Return strict JSON\n\n"
        "DOCUMENT:\n"
        f"{text}"
    )


def _load_model(base_model: str, adapter_path: str):
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    base = AutoModelForCausalLM.from_pretrained(
        base_model, quantization_config=quant_cfg, device_map="auto", trust_remote_code=True
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    model.eval()
    return model, tokenizer


def _get_cached_model(base_model: str, adapter_path: str):
    key = f"{base_model}::{adapter_path}"
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        model, tokenizer = _load_model(base_model, adapter_path)
        _MODEL_CACHE[key] = (model, tokenizer)
        return model, tokenizer


def _generate(model, tokenizer, user_prompt: str, max_new_tokens: int = 256) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    x = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **x,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=0.0,
            top_p=0.8,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][x["input_ids"].shape[1] :]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def _extract_field(field: str, text: str, model, tokenizer, form_type: str = "acord_125", max_new_tokens: int = 128) -> Any:
    raw = _generate(model, tokenizer, build_field_prompt(field, text, form_type=form_type), max_new_tokens=max_new_tokens)
    parsed = validate_json(raw)
    if not parsed:
        return None
    return verify_field(field, parsed.get(field), text, threshold=85.0)


def _multi_field_pipeline(text: str, model, tokenizer, form_type: str = "acord_125", schema: Optional[List[str]] = None) -> Dict[str, Any]:
    schema_keys = schema or FIXED_SCHEMA_KEYS
    result: Dict[str, Any] = {}
    for field in schema_keys:
        result[field] = _extract_field(field, text, model, tokenizer, form_type=form_type)
    return result


def _sanitize_output(data: Dict[str, Any], text: str, grounding_threshold: float, schema_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    cleaned = enforce_schema(data, schema_keys=schema_keys)
    cleaned = enforce_grounding(cleaned, text, threshold=grounding_threshold, schema_keys=schema_keys)
    cleaned = validate_fields(cleaned)
    cleaned = consistency_check(cleaned, text)
    return cleaned


def detect_template(text: str) -> str:
    src = (text or "").upper()
    if "ACORD 125" in src or "COMMERCIAL INSURANCE APPLICATION" in src:
        return "acord_125"
    return "unknown"


def _read_ocr_confidence_from_manifest(ocr_manifest_path: Optional[str], input_text_file: Optional[str]) -> Optional[float]:
    if not ocr_manifest_path or not input_text_file:
        return None
    mf = Path(ocr_manifest_path)
    if not mf.exists():
        return None
    try:
        rows = json.loads(mf.read_text(encoding="utf-8"))
        text_name = Path(input_text_file).name
        for r in rows:
            if str(r.get("text_file", "")) == text_name:
                return float(r.get("ocr_confidence"))
    except Exception:
        return None
    return None


def extract_pipeline(
    text: str,
    model,
    tokenizer,
    secondary_model=None,
    secondary_tokenizer=None,
    grounding_threshold: float = 85.0,
    low_conf_threshold: float = 80.0,
    review_threshold: float = 80.0,
    min_ocr_confidence: float = 0.7,
    ocr_confidence: Optional[float] = None,
    template_name: Optional[str] = None,
    schema: Optional[List[str]] = None,
    metrics_out: Optional[str] = None,
) -> Dict[str, Any]:
    start = time.time()
    if ocr_confidence is not None and ocr_confidence < min_ocr_confidence:
        return {"status": "bad_input", "data": None, "confidence": 0.0}

    template = template_name or detect_template(text)
    if template not in SCHEMA_REGISTRY:
        return {"status": "unsupported_document", "template": template, "data": None, "confidence": 0.0}

    cache_key = hashlib.sha256(
        (text + f"|{grounding_threshold}|{low_conf_threshold}|{review_threshold}").encode("utf-8")
    ).hexdigest()
    if cache_key in _CACHE:
        cached = dict(_CACHE[cache_key])
        cached["cache_hit"] = True
        return cached

    schema_keys = schema or FIXED_SCHEMA_KEYS
    raw_output = _generate(model, tokenizer, build_prompt(text, form_type=template, schema=schema_keys))
    data = validate_json(raw_output)
    if not data:
        return {"status": "invalid_json", "data": None, "confidence": 0.0, "raw_output": raw_output}

    # PASS 1: full extraction
    full_data = _sanitize_output(data, text, grounding_threshold=grounding_threshold, schema_keys=schema_keys)

    # PASS 2: field-wise extraction and verification
    field_data = _sanitize_output(
        _multi_field_pipeline(text, model, tokenizer, form_type=template, schema=schema_keys),
        text,
        grounding_threshold=grounding_threshold,
        schema_keys=schema_keys,
    )

    # Merge strategy: prefer field-wise value when present.
    merged = dict(full_data)
    for key in schema_keys:
        if field_data.get(key) is not None:
            merged[key] = field_data[key]

    # Deterministic override layer
    rules = rule_based_extraction(text)
    for key, value in rules.items():
        if key in FIXED_SCHEMA_KEYS:
            merged[key] = value

    merged = _sanitize_output(merged, text, grounding_threshold=grounding_threshold, schema_keys=schema_keys)

    confidence = compute_confidence(merged, text, schema_keys=schema_keys)
    field_confidence = compute_field_confidence(merged, text, schema_keys=schema_keys)
    field_confidence = apply_field_position_heuristics(merged, text, field_confidence, schema_keys=schema_keys)
    trust_score = compute_trust_score(merged, text, schema_keys=schema_keys)
    final_score = (confidence + (trust_score * 100.0)) / 2.0

    inconsistent_fields: List[str] = []
    if secondary_model is not None and secondary_tokenizer is not None:
        secondary_raw = _generate(secondary_model, secondary_tokenizer, build_prompt(text))
        secondary_json = validate_json(secondary_raw) or {}
        secondary_clean = _sanitize_output(
            secondary_json,
            text,
            grounding_threshold=grounding_threshold,
            schema_keys=schema_keys,
        )
        for key in schema_keys:
            if (secondary_clean.get(key) or None) != (merged.get(key) or None):
                inconsistent_fields.append(key)

    debug_log = {
        "raw_output": raw_output,
        "full_pass": full_data,
        "field_pass": field_data,
        "rule_overrides": rules,
        "final_output": merged,
        "confidence": confidence,
        "trust_score": trust_score,
        "final_score": final_score,
        "field_confidence": field_confidence,
        "inconsistent_fields": inconsistent_fields,
    }

    # Retry once with stricter instruction if score is low.
    if final_score < 70.0:
        retry_raw = _generate(model, tokenizer, build_retry_prompt(text, form_type=template, schema=schema_keys))
        retry_data = validate_json(retry_raw) or {}
        retry_clean = _sanitize_output(
            retry_data,
            text,
            grounding_threshold=grounding_threshold,
            schema_keys=schema_keys,
        )
        retry_conf = compute_confidence(retry_clean, text, schema_keys=schema_keys)
        retry_trust = compute_trust_score(retry_clean, text, schema_keys=schema_keys)
        retry_score = (retry_conf + (retry_trust * 100.0)) / 2.0
        if retry_score > final_score:
            merged = retry_clean
            confidence = retry_conf
            trust_score = retry_trust
            final_score = retry_score
            debug_log["retry_raw_output"] = retry_raw
            debug_log["retry_final_output"] = retry_clean
            debug_log["retry_final_score"] = retry_score
            field_confidence = apply_field_position_heuristics(
                merged,
                text,
                compute_field_confidence(merged, text, schema_keys=schema_keys),
                schema_keys=schema_keys,
            )

    status = "ok"
    weak_fields = [k for k, v in field_confidence.items() if k in schema_keys and v < review_threshold]
    if weak_fields:
        status = "needs_review"
    elif final_score < low_conf_threshold:
        status = "low_confidence"
    result = {
        "status": status,
        "data": (merged if status == "ok" else merged),
        "confidence": confidence,
        "field_confidence": field_confidence,
        "review_fields": weak_fields,
        "trust_score": trust_score,
        "final_score": final_score,
        "debug_log": debug_log,
    }
    if status == "needs_review":
        result["fields"] = weak_fields

    elapsed_ms = int((time.time() - start) * 1000)
    if metrics_out:
        line = {
            "status": status,
            "confidence": confidence,
            "trust_score": trust_score,
            "final_score": final_score,
            "retry_used": "retry_final_score" in debug_log,
            "needs_review": status == "needs_review",
            "weak_fields_count": len(weak_fields),
            "inconsistent_fields_count": len(inconsistent_fields),
            "elapsed_ms": elapsed_ms,
        }
        p = Path(metrics_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    _CACHE[cache_key] = dict(result)
    return result


def run_batch_texts(
    text_files: List[Path],
    model,
    tokenizer,
    secondary_model=None,
    secondary_tokenizer=None,
    **kwargs,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in text_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        r = extract_pipeline(
            text=text,
            model=model,
            tokenizer=tokenizer,
            secondary_model=secondary_model,
            secondary_tokenizer=secondary_tokenizer,
            **kwargs,
        )
        r["input_file"] = str(f)
        out.append(r)
    return out


def run_default_extraction(
    text: str,
    *,
    form_type: str = "acord_125",
    ocr_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Runtime helper for backend routes:
    Loads model/adapter from env and runs hardened extraction with cached model.
    """
    base_model = (os.getenv("ACORD_HARDENED_BASE_MODEL") or os.getenv("FINE_TUNE_BASE_MODEL") or "Qwen/Qwen2.5-14B-Instruct").strip()
    adapter_path = (os.getenv("ACORD_HARDENED_ADAPTER_PATH") or os.getenv("CURRENT_ADAPTER_PATH") or "").strip()
    if not adapter_path:
        return {"status": "disabled", "reason": "missing_adapter_path", "data": None}
    if not Path(adapter_path).exists():
        return {"status": "disabled", "reason": "adapter_not_found", "data": None}

    model, tokenizer = _get_cached_model(base_model, adapter_path)
    return extract_pipeline(
        text=text,
        model=model,
        tokenizer=tokenizer,
        template_name=form_type,
        ocr_confidence=ocr_confidence,
        grounding_threshold=float(os.getenv("ACORD_HARDENED_GROUNDING_THRESHOLD", "85.0")),
        low_conf_threshold=float(os.getenv("ACORD_HARDENED_LOW_CONFIDENCE_THRESHOLD", "80.0")),
        review_threshold=float(os.getenv("ACORD_HARDENED_REVIEW_THRESHOLD", "80.0")),
        min_ocr_confidence=float(os.getenv("ACORD_HARDENED_MIN_OCR_CONFIDENCE", "0.7")),
        metrics_out=(os.getenv("ACORD_HARDENED_METRICS_OUT") or "").strip() or None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Production ACORD extraction with firewall validation.")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-14B-Instruct")
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--input-text", help="Raw/clean OCR text")
    parser.add_argument("--input-text-file", help="Path to OCR text file")
    parser.add_argument("--input-text-dir", help="Directory of OCR text files for batch mode")
    parser.add_argument("--secondary-base-model", help="Optional second model for cross-check")
    parser.add_argument("--secondary-adapter-path", help="Optional second adapter path for cross-check")
    parser.add_argument("--ocr-manifest-path", help="Optional OCR manifest path for confidence lookup")
    parser.add_argument("--grounding-threshold", type=float, default=85.0)
    parser.add_argument("--low-confidence-threshold", type=float, default=80.0)
    parser.add_argument("--review-threshold", type=float, default=80.0)
    parser.add_argument("--min-ocr-confidence", type=float, default=0.7)
    parser.add_argument("--metrics-out", help="Append metrics JSONL path")
    args = parser.parse_args()

    model, tokenizer = _load_model(args.base_model, args.adapter_path)
    secondary_model, secondary_tokenizer = (None, None)
    if args.secondary_base_model and args.secondary_adapter_path:
        secondary_model, secondary_tokenizer = _load_model(args.secondary_base_model, args.secondary_adapter_path)

    common_kwargs = dict(
        grounding_threshold=args.grounding_threshold,
        low_conf_threshold=args.low_confidence_threshold,
        review_threshold=args.review_threshold,
        min_ocr_confidence=args.min_ocr_confidence,
        metrics_out=args.metrics_out,
    )

    if args.input_text_dir:
        files = sorted(Path(args.input_text_dir).glob("*.txt"))
        results = run_batch_texts(
            files,
            model=model,
            tokenizer=tokenizer,
            secondary_model=secondary_model,
            secondary_tokenizer=secondary_tokenizer,
            **common_kwargs,
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not args.input_text and not args.input_text_file:
        raise SystemExit("Provide --input-text, --input-text-file, or --input-text-dir")
    text = args.input_text or Path(args.input_text_file).read_text(encoding="utf-8", errors="replace")
    ocr_conf = _read_ocr_confidence_from_manifest(args.ocr_manifest_path, args.input_text_file)
    template = detect_template(text)
    result = extract_pipeline(
        text=text,
        model=model,
        tokenizer=tokenizer,
        secondary_model=secondary_model,
        secondary_tokenizer=secondary_tokenizer,
        ocr_confidence=ocr_conf,
        template_name=template,
        **common_kwargs,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

