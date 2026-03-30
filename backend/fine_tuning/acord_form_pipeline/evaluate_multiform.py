from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from .inference_production import _load_model, extract_pipeline
from .postprocess import validate_json
from .schema_registry import IMPORTANT_FIELDS, SCHEMA_REGISTRY, normalize_aliases_for_schema


def evaluate_multiform(dataset_jsonl: Path, base_model: str, adapter_path: str, out_report: Path) -> Dict[str, Any]:
    rows = [json.loads(x) for x in dataset_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    model, tokenizer = _load_model(base_model, adapter_path)

    per_form = defaultdict(
        lambda: {
            "n": 0,
            "json_valid": 0,
            "field_total": 0,
            "field_match": 0,
            "business_total": 0,
            "business_match": 0,
        }
    )

    for r in rows:
        form_type = r.get("form_type", "unknown")
        metrics = per_form[form_type]
        metrics["n"] += 1
        msgs = r["messages"]
        text = msgs[1]["content"].split("Document:\n", 1)[-1]
        ref = normalize_aliases_for_schema(validate_json(msgs[2]["content"]) or {}, form_type)
        pred = extract_pipeline(text=text, model=model, tokenizer=tokenizer, template_name=form_type)
        data = normalize_aliases_for_schema(pred.get("data") or {}, form_type)
        if pred.get("status") in {"ok", "needs_review", "low_confidence"}:
            metrics["json_valid"] += 1
        schema = SCHEMA_REGISTRY.get(form_type, list(ref.keys()))
        for k in schema:
            metrics["field_total"] += 1
            if data.get(k) == ref.get(k):
                metrics["field_match"] += 1
        for bk in IMPORTANT_FIELDS:
            if bk in schema:
                metrics["business_total"] += 1
                if data.get(bk) == ref.get(bk):
                    metrics["business_match"] += 1

    report: Dict[str, Any] = {}
    for ft, m in per_form.items():
        n = max(m["n"], 1)
        report[ft] = {
            "samples": m["n"],
            "json_valid_percent": 100.0 * (m["json_valid"] / n),
            "field_accuracy_percent": 100.0 * (m["field_match"] / max(m["field_total"], 1)),
            "business_accuracy_percent": 100.0 * (m["business_match"] / max(m["business_total"], 1)),
        }
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="Per-form evaluation for multi-form ACORD extraction.")
    p.add_argument("--dataset", required=True)
    p.add_argument("--base-model", default="Qwen/Qwen2.5-14B-Instruct")
    p.add_argument("--adapter-path", required=True)
    p.add_argument("--report-out", default="fine_tuning/runs/acord_multiform_eval.json")
    args = p.parse_args()
    rep = evaluate_multiform(Path(args.dataset), args.base_model, args.adapter_path, Path(args.report_out))
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()

