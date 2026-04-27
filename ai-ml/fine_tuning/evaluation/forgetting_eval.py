"""
Forgetting evaluator — measure catastrophic forgetting vs. the parent version.

Compares field_recall on the parent version's eval examples before and after
the new fine-tuning cycle.  A large drop signals catastrophic forgetting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fine_tuning.evaluation.local_metrics import LocalEvalResult, run_local_eval


@dataclass
class ForgettingResult:
    recall_drop: float          # parent_recall − current_recall  (positive = drop)
    parent_recall: float
    current_recall: float
    skipped: bool = False
    skip_reason: str = ""


class ForgettingEvaluator:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    def evaluate(
        self,
        adapter_path: str,
        parent_eval_examples: List[Dict[str, Any]],
        parent_version_scores: Optional[Dict[str, Any]] = None,
    ) -> ForgettingResult:
        """
        Run the adapter on parent_eval_examples and compare recall to the
        parent version's known recall score.

        Parameters
        ----------
        adapter_path         : path to the newly-trained LoRA adapter
        parent_eval_examples : eval set used to score the parent version
                               format: [{"user_content": str, "expected_fields": dict}]
        parent_version_scores: dict with "field_recall" key (from registry eval_scores)
        """
        if not parent_eval_examples:
            return ForgettingResult(
                recall_drop=0.0,
                parent_recall=0.0,
                current_recall=0.0,
                skipped=True,
                skip_reason="no parent eval examples provided",
            )

        parent_recall = float(
            (parent_version_scores or {}).get("field_recall", 0.0)
        )

        current_result: LocalEvalResult = run_local_eval(
            adapter_path, self._config, parent_eval_examples
        )

        if current_result.skipped:
            return ForgettingResult(
                recall_drop=0.0,
                parent_recall=parent_recall,
                current_recall=0.0,
                skipped=True,
                skip_reason=current_result.skip_reason,
            )

        recall_drop = parent_recall - current_result.field_recall
        return ForgettingResult(
            recall_drop=max(0.0, recall_drop),
            parent_recall=parent_recall,
            current_recall=current_result.field_recall,
        )
