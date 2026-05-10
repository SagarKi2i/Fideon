from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from fine_tuning.acord_eval_normalize import (
    normalize_scalar_for_compare,
    oos_refusal_match,
)
from fine_tuning.acord_training_targets import build_sft_label_json
from fine_tuning.oos_refusal_examples import OOS_SYSTEM_RULES

from .postprocess import compute_confidence, enforce_grounding, enforce_schema, validate_fields, validate_json
from .schema import FIXED_SCHEMA_KEYS, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger("acord125.eval")


def _is_hallucinated(value: Any, input_text: str) -> bool:
    grounded = enforce_grounding({"x": value}, input_text, threshold=85.0)
    return grounded.get("x") is None and value is not None


def _generate(model, tokenizer, input_text: str, max_new_tokens: int = 256, *, oos: bool = False) -> str:
    if oos:
        sys_prompt = OOS_SYSTEM_RULES
    else:
        sys_prompt = SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(input_text=input_text)},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    x = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **x,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=0.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][x["input_ids"].shape[1] :]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def _fields_equal(a: Any, b: Any) -> bool:
    return normalize_scalar_for_compare(a) == normalize_scalar_for_compare(b)


def _field_metrics_in_domain(ref_full: Dict[str, Any], pred_full: Dict[str, Any], keys: List[str]) -> Tuple[float, float]:
    """Micro recall / precision on six-field schema; null expected fields ignored for recall denom."""
    exp_non_null = [k for k in keys if ref_full.get(k) is not None]
    pred_non_null = [k for k in keys if pred_full.get(k) is not None]
    matched_exp = sum(
        1 for k in exp_non_null if _fields_equal(pred_full.get(k), ref_full.get(k))
    )
    recall = matched_exp / max(len(exp_non_null), 1)
    if not pred_non_null:
        prec = 1.0
    else:
        prec = sum(1 for k in pred_non_null if _fields_equal(pred_full.get(k), ref_full.get(k))) / len(
            pred_non_null
        )
    return recall, prec


def evaluate(dataset_jsonl: Path, base_model: str, adapter_path: Path, report_out: Path) -> Dict[str, Any]:
    rows = [json.loads(line) for line in dataset_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    oos_expected = sum(
        1
        for row in rows
        if (row.get("record_meta") or {}).get("oos")
        or (row.get("record_meta") or {}).get("category") == "oos"
    )

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
    model = PeftModel.from_pretrained(base, str(adapter_path))
    model.eval()

    json_ok = 0
    id_valid = 0
    id_schema_ok = 0
    id_exact = 0
    id_field_total = 0
    id_field_match = 0
    id_hall = 0
    id_hall_checks = 0
    id_recall_sum = 0.0
    id_prec_sum = 0.0
    id_recall_n = 0

    oos_refusal_ok = 0

    failed_examples: List[Dict[str, Any]] = []
    assert_build_sft_called = False

    for idx, row in enumerate(rows):
        msgs = row["messages"]
        meta = row.get("record_meta") or {}
        is_oos = bool(meta.get("oos")) or meta.get("category") == "oos"
        input_text = msgs[1]["content"].split("Document:\n", 1)[-1]
        assistant_raw = msgs[2]["content"]

        ref_raw = validate_json(assistant_raw) or {}
        if not is_oos:
            _ = build_sft_label_json(ref_raw)
            assert_build_sft_called = True

        pred_text = _generate(model, tokenizer, input_text=input_text, oos=is_oos)
        pred_raw = validate_json(pred_text)
        if pred_raw is None:
            failed_examples.append({"index": idx, "reason": "invalid_json", "prediction": pred_text[:500]})
            continue

        json_ok += 1

        if is_oos or ref_raw.get("error") == "not_acord_125":
            if oos_refusal_match(pred_text):
                oos_refusal_ok += 1
            elif len(failed_examples) < 20:
                failed_examples.append(
                    {"index": idx, "reason": "oos_mismatch", "prediction": pred_text[:500], "reference": ref_raw}
                )
            continue

        pred_proc = enforce_schema(pred_raw)
        pred_proc = enforce_grounding(pred_proc, input_text, threshold=85.0)
        pred_proc = validate_fields(pred_proc)
        ref_full = build_sft_label_json(ref_raw)

        id_valid += 1

        if all(k in pred_proc for k in FIXED_SCHEMA_KEYS):
            id_schema_ok += 1

        row_exact = True
        for k in FIXED_SCHEMA_KEYS:
            id_field_total += 1
            pv = pred_proc.get(k)
            rv = ref_full.get(k)
            if _fields_equal(pv, rv):
                id_field_match += 1
            else:
                row_exact = False
            id_hall_checks += 1
            if _is_hallucinated(pred_proc.get(k), input_text):
                id_hall += 1

        rec, prec = _field_metrics_in_domain(ref_full, pred_proc, list(FIXED_SCHEMA_KEYS))
        id_recall_sum += rec
        id_prec_sum += prec
        id_recall_n += 1

        if row_exact:
            id_exact += 1
        if not row_exact and len(failed_examples) < 20:
            pred_cmp = {k: pred_proc.get(k) for k in FIXED_SCHEMA_KEYS}
            ref_cmp = {k: ref_full.get(k) for k in FIXED_SCHEMA_KEYS}
            failed_examples.append(
                {"index": idx, "reason": "field_mismatch", "prediction": pred_cmp, "reference": ref_cmp}
            )

    n = max(len(rows), 1)
    n_id = max(id_valid, 1)

    report = {
        "samples": len(rows),
        "samples_in_domain": id_valid,
        "samples_oos": oos_expected,
        "json_valid_percent": json_ok / n * 100.0,
        "schema_accuracy_percent": (id_schema_ok / n_id) * 100.0 if id_valid else 0.0,
        "exact_match_percent": (id_exact / n_id) * 100.0 if id_valid else 0.0,
        "field_accuracy_percent": (id_field_match / max(id_field_total, 1)) * 100.0,
        "field_recall_percent": (id_recall_sum / max(id_recall_n, 1)) * 100.0,
        "field_precision_percent": (id_prec_sum / max(id_recall_n, 1)) * 100.0,
        "hallucination_rate_percent": (id_hall / max(id_hall_checks, 1)) * 100.0,
        "refusal_accuracy_percent": (oos_refusal_ok / max(oos_expected, 1)) * 100.0 if oos_expected else 0.0,
        "mean_grounded_confidence": 0.0,
        "failed_examples": failed_examples,
        "assert_build_sft_label_json_on_gt": assert_build_sft_called,
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("JSON valid: %.2f%%", report["json_valid_percent"])
    logger.info("Field recall (avg): %.2f%%", report["field_recall_percent"])
    logger.info("Field precision (avg): %.2f%%", report["field_precision_percent"])
    logger.info("Refusal accuracy (OOS): %.2f%%", report["refusal_accuracy_percent"])
    for ex in failed_examples[:5]:
        logger.info("Failed example idx=%s reason=%s", ex.get("index"), ex.get("reason"))
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description="Evaluate ACORD extraction adapter quality.")
    parser.add_argument("--dataset", required=True, help="Unseen test JSONL in chat format")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-14B-Instruct")
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--report-out", default="fine_tuning/runs/acord_eval_report.json")
    args = parser.parse_args()
    evaluate(
        dataset_jsonl=Path(args.dataset),
        base_model=args.base_model,
        adapter_path=Path(args.adapter_path),
        report_out=Path(args.report_out),
    )


if __name__ == "__main__":
    main()
