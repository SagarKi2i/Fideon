"""
Three-tier quality gate for ACORD fine-tuning deploy decisions.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def evaluate_acord_gate(eval_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns gate_tier, deploy_recommended, gate_reasons, metrics.

    PASS: deploy adapter with confidence.
    WARN: deploy_recommended true with monitoring (below PASS but meets WARN floors).
    FAIL: do not deploy.
    """
    results = eval_payload.get("results") or {}
    if not isinstance(results, dict):
        return {
            "gate_tier": "FAIL",
            "deploy_recommended": False,
            "gate_reasons": ["missing evaluation results"],
            "metrics": {},
        }

    seen = results.get("seen") or {}
    oos = results.get("out_of_scope") or {}

    json_valid = _f(seen.get("json_valid_rate"))
    field_recall = _f(seen.get("json_field_recall"))
    field_precision = _f(seen.get("json_field_precision"))
    oos_hall = _f(oos.get("hallucination_rate"))
    refusal_acc = _f(oos.get("refusal_accuracy") or oos.get("refusal_rate"))

    metrics = {
        "json_valid_rate": json_valid,
        "field_recall": field_recall,
        "field_precision": field_precision,
        "oos_hallucination_rate": oos_hall,
        "oos_refusal_accuracy": refusal_acc,
    }

    pass_json = float(os.getenv("FT_ACORD_GATE_PASS_JSON_VALID", "0.95"))
    pass_recall = float(os.getenv("FT_ACORD_GATE_PASS_FIELD_RECALL", "0.75"))
    pass_oos_hall = float(os.getenv("FT_ACORD_GATE_PASS_OOS_HALLUC", "0.15"))
    pass_refusal = float(os.getenv("FT_ACORD_GATE_PASS_REFUSAL_ACC", "0.60"))

    warn_json = float(os.getenv("FT_ACORD_GATE_WARN_JSON_VALID", "0.90"))
    warn_recall = float(os.getenv("FT_ACORD_GATE_WARN_FIELD_RECALL", "0.60"))
    warn_oos_hall = float(os.getenv("FT_ACORD_GATE_WARN_OOS_HALLUC", "0.40"))

    def pass_violations() -> List[str]:
        v: List[str] = []
        if json_valid < pass_json:
            v.append(f"json_valid {json_valid:.4f} < {pass_json} (PASS bar)")
        if field_recall < pass_recall:
            v.append(f"field_recall {field_recall:.4f} < {pass_recall} (PASS bar)")
        if oos_hall > pass_oos_hall:
            v.append(f"oos_hallucination_rate {oos_hall:.4f} > {pass_oos_hall} (PASS bar)")
        if refusal_acc < pass_refusal:
            v.append(f"refusal_accuracy {refusal_acc:.4f} < {pass_refusal} (PASS bar)")
        return v

    def warn_violations() -> List[str]:
        v: List[str] = []
        if json_valid < warn_json:
            v.append(f"json_valid {json_valid:.4f} < {warn_json} (WARN floor)")
        if field_recall < warn_recall:
            v.append(f"field_recall {field_recall:.4f} < {warn_recall} (WARN floor)")
        if oos_hall > warn_oos_hall:
            v.append(f"oos_hallucination_rate {oos_hall:.4f} > {warn_oos_hall} (WARN floor)")
        return v

    pv = pass_violations()
    if not pv:
        return {
            "gate_tier": "PASS",
            "deploy_recommended": True,
            "gate_reasons": [],
            "metrics": metrics,
        }

    wv = warn_violations()
    if not wv:
        return {
            "gate_tier": "WARN",
            "deploy_recommended": True,
            "gate_reasons": pv,
            "metrics": metrics,
        }

    return {
        "gate_tier": "FAIL",
        "deploy_recommended": False,
        "gate_reasons": pv + wv,
        "metrics": metrics,
    }


def gate_should_fail_job(gate: Dict[str, Any]) -> bool:
    return gate.get("gate_tier") == "FAIL"
