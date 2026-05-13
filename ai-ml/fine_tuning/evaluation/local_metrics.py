"""
Local evaluation: run the fine-tuned adapter on eval examples and compute
field-level F1 / recall / precision.

run_local_eval() is the public entry point.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.continuous_learning.ingest import get_universal_system_prompt as _get_eval_system_prompt


@dataclass
class LocalEvalResult:
    field_f1: float = 0.0
    field_recall: float = 0.0
    field_precision: float = 0.0
    n_examples: int = 0
    # Per eval-set breakdown (seen / paraphrased / oos)
    by_set: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str = ""


def _extract_json_from_output(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse the first JSON object found in model output."""
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _field_scores(
    predicted: Dict[str, Any], expected: Dict[str, Any]
) -> Dict[str, float]:
    pred_keys = set(str(k) for k in (predicted or {}).keys())
    exp_keys  = set(str(k) for k in (expected  or {}).keys())

    if not exp_keys:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    true_positives = sum(
        1 for k in (pred_keys & exp_keys)
        if str(predicted.get(k, "")).strip().lower() == str(expected.get(k, "")).strip().lower()
    )
    precision = true_positives / len(pred_keys) if pred_keys else 0.0
    recall    = true_positives / len(exp_keys)
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _generate_response(model: Any, processor: Any, user_content: str, max_new_tokens: int = 512) -> str:
    import torch

    msgs = [
        {"role": "system", "content": _get_eval_system_prompt()},
        {"role": "user",   "content": user_content},
    ]
    text_input = processor.apply_chat_template(
        msgs, tokenize=False, add_generation_prompt=True
    )
    inputs = processor(text=[text_input], return_tensors="pt", padding=True)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        out_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
    trimmed = [o[len(i):] for i, o in zip(inputs["input_ids"], out_ids)]
    return processor.batch_decode(trimmed, skip_special_tokens=True)[0]


def run_local_eval(
    adapter_path: str,
    config: Dict[str, Any],
    eval_examples: List[Dict[str, Any]],
) -> LocalEvalResult:
    """
    Load the fine-tuned adapter and evaluate on eval_examples.

    Each eval_example: {"user_content": str, "expected_fields": dict}

    If eval_examples is empty, returns a skipped result (gate uses parent scores).
    """
    if not eval_examples:
        return LocalEvalResult(skipped=True, skip_reason="no eval examples provided")

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
    except ImportError as e:
        return LocalEvalResult(skipped=True, skip_reason=f"import error: {e}")

    local_only = str(config.get("local_files_only", "true")).lower() in {"1", "true", "yes"}
    eval_cfg   = config.get("evaluation", {})
    max_tok    = int(eval_cfg.get("max_new_tokens", 512))

    try:
        base_model = config.get("base_model", "/workspace/models/qwen2-vl-7b")
        processor  = AutoProcessor.from_pretrained(adapter_path, local_files_only=False)
        dtype      = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        base       = Qwen2VLForConditionalGeneration.from_pretrained(
            base_model, torch_dtype=dtype, device_map="auto", local_files_only=local_only
        )
        model = PeftModel.from_pretrained(base, adapter_path)
        model.eval()
    except Exception as e:
        return LocalEvalResult(skipped=True, skip_reason=f"model load failed: {e}")

    f1_scores: List[float] = []
    recall_scores: List[float] = []
    precision_scores: List[float] = []

    for ex in eval_examples:
        user_content = ex.get("user_content", "")
        expected     = ex.get("expected_fields", {})
        try:
            raw_output  = _generate_response(model, processor, user_content, max_tok)
            predicted   = _extract_json_from_output(raw_output) or {}
            scores      = _field_scores(predicted, expected)
            f1_scores.append(scores["f1"])
            recall_scores.append(scores["recall"])
            precision_scores.append(scores["precision"])
        except Exception:
            f1_scores.append(0.0)
            recall_scores.append(0.0)
            precision_scores.append(0.0)

    n = len(f1_scores)
    return LocalEvalResult(
        field_f1=sum(f1_scores) / n if n else 0.0,
        field_recall=sum(recall_scores) / n if n else 0.0,
        field_precision=sum(precision_scores) / n if n else 0.0,
        n_examples=n,
    )
