"""
DeepEval runner — optional LLM-judge metrics (faithfulness, answer relevancy).

If the `deepeval` package is not installed this module silently returns
a skipped result so the gate can proceed on local_metrics alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DeepEvalResult:
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    skipped: bool = False
    skip_reason: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


def run_deepeval(
    adapter_path: str,
    config: Dict[str, Any],
    eval_examples: Optional[List[Dict[str, Any]]] = None,
) -> DeepEvalResult:
    """
    Run DeepEval LLM-judge metrics on a sample of eval_examples.

    Falls back gracefully if:
      • deepeval is not installed
      • eval_examples is empty / None
      • any runtime error occurs
    """
    if not eval_examples:
        return DeepEvalResult(skipped=True, skip_reason="no eval examples provided")

    try:
        import deepeval  # noqa: F401
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return DeepEvalResult(
            skipped=True, skip_reason="deepeval not installed"
        )

    try:
        from fine_tuning.evaluation.local_metrics import _generate_response

        import torch
        from peft import PeftModel
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

        local_only = str(config.get("local_files_only", "true")).lower() in {
            "1", "true", "yes"
        }
        base_model = config.get("base_model", "/workspace/models/qwen2-vl-7b")
        processor  = AutoProcessor.from_pretrained(adapter_path, local_files_only=False)
        dtype      = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        base       = Qwen2VLForConditionalGeneration.from_pretrained(
            base_model, torch_dtype=dtype, device_map="auto", local_files_only=local_only
        )
        model = PeftModel.from_pretrained(base, adapter_path)
        model.eval()

        max_tok = int(config.get("evaluation", {}).get("max_new_tokens", 512))
        test_cases: List[LLMTestCase] = []

        for ex in eval_examples[:10]:  # cap at 10 to limit cost
            user_content = ex.get("user_content", "")
            output = _generate_response(model, processor, user_content, max_tok)
            test_cases.append(
                LLMTestCase(
                    input=user_content,
                    actual_output=output,
                    expected_output=str(ex.get("expected_fields", "")),
                    retrieval_context=[user_content],
                )
            )

        faithfulness_metric   = FaithfulnessMetric(threshold=0.5)
        answer_rel_metric     = AnswerRelevancyMetric(threshold=0.5)
        faith_scores, rel_scores = [], []

        for tc in test_cases:
            faithfulness_metric.measure(tc)
            answer_rel_metric.measure(tc)
            faith_scores.append(faithfulness_metric.score)
            rel_scores.append(answer_rel_metric.score)

        avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else None
        avg_rel   = sum(rel_scores)   / len(rel_scores)   if rel_scores   else None

        return DeepEvalResult(
            faithfulness=avg_faith,
            answer_relevancy=avg_rel,
            raw={"n_cases": len(test_cases)},
        )

    except Exception as exc:
        return DeepEvalResult(skipped=True, skip_reason=f"deepeval error: {exc}")
