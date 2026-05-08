"""
Dataset schema for instruction-response fine-tuning.

Each sample should have:
  - instruction: question or task
  - input: optional context (can be empty string)
  - output: expected model response

Optional fields: domain, id, source.
"""

import json
from typing import Any, List, Optional

# Expected keys per example
REQUIRED_KEYS = {"instruction", "output"}
OPTIONAL_KEYS = {"input", "domain", "id", "source", "instruction_type"}

# Instruction types for evaluation (seen / paraphrased / out_of_scope)
TYPE_SEEN = "seen"
TYPE_PARAPHRASED = "paraphrased"
TYPE_OUT_OF_SCOPE = "out_of_scope"


def validate_example(example: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Check one example has required keys and string values. Returns (ok, error_msg)."""
    if not isinstance(example, dict):
        return False, "Example must be a dict"
    missing = REQUIRED_KEYS - set(example)
    if missing:
        return False, f"Missing keys: {missing}"
    for key in REQUIRED_KEYS:
        if not isinstance(example.get(key), str):
            return False, f"'{key}' must be a string"
    if "input" in example and example["input"] is not None and not isinstance(example["input"], str):
        return False, "'input' must be a string or omitted"
    return True, None


def validate_dataset(
    data: List[dict[str, Any]],
    *,
    require_json_output: bool = False,
) -> tuple[bool, List[str]]:
    """Validate examples and optionally require output to be valid JSON."""
    errors: List[str] = []
    for i, ex in enumerate(data):
        ok, msg = validate_example(ex)
        if not ok:
            errors.append(f"Sample {i}: {msg}")
            continue
        if require_json_output:
            try:
                json.loads(ex.get("output", ""))
            except Exception:
                errors.append(
                    f"Sample {i}: output is not valid JSON (set require_json_output=false to allow plain text)"
                )
    return len(errors) == 0, errors
