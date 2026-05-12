"""
Evaluation gate — decide whether a newly-trained adapter should be promoted.

run_eval_gate() checks:
  1. Absolute floors   — field_f1 and field_recall must meet minimum thresholds
  2. Regression guard  — scores must not drop > max_regression vs parent version
  3. Improvement check — optional minimum improvement over parent
  4. Forgetting guard  — recall on parent eval set must not drop > max_forgetting_drop
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.evaluation.local_metrics import LocalEvalResult
from fine_tuning.evaluation.forgetting_eval import ForgettingResult


@dataclass
class GateDecision:
    passed: bool
    failures: List[str]
    scores: Dict[str, Any]


def run_eval_gate(
    local_result: LocalEvalResult,
    deepeval_result: Any,                        # DeepEvalResult | None
    parent_version_scores: Optional[Dict[str, Any]],
    config: Dict[str, Any],
    forgetting_result: Optional[ForgettingResult] = None,
) -> GateDecision:
    """
    Apply quality gate.  Returns GateDecision(passed=True/False, failures=[...]).
    """
    eval_cfg = config.get("evaluation", {})
    floors   = eval_cfg.get("absolute_floors", {})
    min_f1        = float(floors.get("field_f1",      0.65))
    min_recall    = float(floors.get("field_recall",  0.60))
    max_regression = float(eval_cfg.get("max_regression",     0.05))
    min_improvement = float(eval_cfg.get("min_improvement",   0.0))
    max_forgetting  = float(eval_cfg.get("max_forgetting_drop", 0.10))

    failures: List[str] = []
    scores: Dict[str, Any] = {}

    # ── Skip gate if eval was skipped (no examples) ───────────────────────────
    # No eval examples means we cannot verify model quality — block promotion
    # unless the config explicitly sets allow_skip_eval_gate: true.
    if local_result.skipped:
        allow_skip = bool(eval_cfg.get("allow_skip_eval_gate", True))
        if allow_skip:
            print(
                "[eval_gate] WARNING: no eval examples — gate skipped (allow_skip_eval_gate=true). "
                "Add eval samples to catch broken models before promotion."
            )
            return GateDecision(
                passed=True,
                failures=[],
                scores={"skipped": True, "reason": local_result.skip_reason},
            )
        return GateDecision(
            passed=False,
            failures=[
                f"No evaluation examples found ({local_result.skip_reason}). "
                "Add eval examples to /workspace/fine_tuning/eval/ so model quality "
                "can be verified before promotion. Or set allow_skip_eval_gate: true "
                "in config to override (not recommended for production)."
            ],
            scores={"skipped": True, "reason": local_result.skip_reason},
        )

    scores["field_f1"]        = round(local_result.field_f1,        4)
    scores["field_recall"]    = round(local_result.field_recall,    4)
    scores["field_precision"] = round(local_result.field_precision, 4)
    scores["n_examples"]      = local_result.n_examples

    # ── 1. Absolute floors ────────────────────────────────────────────────────
    if local_result.field_f1 < min_f1:
        failures.append(
            f"field_f1 {local_result.field_f1:.4f} < floor {min_f1:.4f}"
        )
    if local_result.field_recall < min_recall:
        failures.append(
            f"field_recall {local_result.field_recall:.4f} < floor {min_recall:.4f}"
        )

    # ── 2. Regression guard vs parent ─────────────────────────────────────────
    if parent_version_scores:
        parent_f1     = float(parent_version_scores.get("field_f1",     0.0))
        parent_recall = float(parent_version_scores.get("field_recall", 0.0))
        scores["parent_field_f1"]     = parent_f1
        scores["parent_field_recall"] = parent_recall

        f1_delta     = local_result.field_f1     - parent_f1
        recall_delta = local_result.field_recall - parent_recall

        if f1_delta < -max_regression:
            failures.append(
                f"field_f1 regression {f1_delta:.4f} exceeds allowed -{max_regression:.4f}"
            )
        if recall_delta < -max_regression:
            failures.append(
                f"field_recall regression {recall_delta:.4f} exceeds allowed -{max_regression:.4f}"
            )

        # ── 3. Improvement check ──────────────────────────────────────────────
        if min_improvement > 0:
            if f1_delta < min_improvement and recall_delta < min_improvement:
                failures.append(
                    f"no improvement: f1_delta={f1_delta:.4f}, "
                    f"recall_delta={recall_delta:.4f} "
                    f"(required ≥{min_improvement:.4f})"
                )

    # ── 4. Forgetting guard ───────────────────────────────────────────────────
    if forgetting_result and not forgetting_result.skipped:
        scores["forgetting_drop"] = round(forgetting_result.recall_drop, 4)
        if forgetting_result.recall_drop > max_forgetting:
            failures.append(
                f"forgetting_drop {forgetting_result.recall_drop:.4f} "
                f"> max {max_forgetting:.4f}"
            )

    return GateDecision(passed=len(failures) == 0, failures=failures, scores=scores)
