"""
Load and format training/eval data for instruction-response fine-tuning.

Supports:
- JSON or JSONL dataset (instruction, input, output)
- Train/validation split
- Prompt formatting for SFT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .schema import validate_dataset


def format_oos_chat_sft(tokenizer: Any, example: Dict[str, Any]) -> str:
    """Chat template for OOS refusal JSON (must match eval generation for OOS rows)."""
    from .acord_form_pipeline.schema import USER_PROMPT_TEMPLATE
    from .oos_refusal_examples import OOS_SYSTEM_RULES

    input_text = example.get("input") or ""
    output_text = (example.get("output") or "").strip()
    messages = [
        {"role": "system", "content": OOS_SYSTEM_RULES},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(input_text=input_text)},
        {"role": "assistant", "content": output_text},
    ]
    if not getattr(tokenizer, "chat_template", None):
        return format_prompt(example)
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def format_acord_chat_sft(tokenizer: Any, example: Dict[str, Any]) -> str:
    """
    Build SFT text using the same chat layout as acord_form_pipeline.evaluate_extraction
    (system + user Document + assistant JSON). Required so Qwen Instruct learns the
    same distribution as generation at eval time.
    """
    from .acord_form_pipeline.schema import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

    input_text = example.get("input") or ""
    output_text = (example.get("output") or "").strip()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(input_text=input_text)},
        {"role": "assistant", "content": output_text},
    ]
    if not getattr(tokenizer, "chat_template", None):
        return format_prompt(example)
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def load_dataset_json(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load a JSON array or JSONL file into a list of examples."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() == ".jsonl" or (
        "\n" in text and text.count("\n") >= 1 and not text.strip().startswith("[")
    ):
        # JSONL: one JSON object per line
        data = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            data.append(__import__("json").loads(line))
        return data

    import json
    raw = json.loads(text)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "data" in raw:
        return raw["data"]
    if isinstance(raw, dict) and "examples" in raw:
        return raw["examples"]
    return [raw]


def format_prompt(example: Dict[str, Any], template: Optional[str] = None) -> str:
    """
    Convert one example into a single prompt string for SFT.

    Default template:
      ### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}
    """
    instruction = example.get("instruction", "")
    input_text = example.get("input") or ""
    output = example.get("output", "")

    if template is None:
        template = (
            "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}"
        )
    return template.format(
        instruction=instruction,
        input=input_text,
        output=output,
    )


def format_prompt_for_inference(instruction: str, input_text: str = "") -> str:
    """Format only instruction + input (no output) for generation."""
    return (
        "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n"
    ).format(instruction=instruction, input=input_text or "")


def prepare_dataset(
    dataset_path: Union[str, Path],
    *,
    max_samples: Optional[int] = None,
    validate: bool = True,
) -> List[Dict[str, Any]]:
    """
    Load, validate, and optionally cap dataset size.
    """
    data = load_dataset_json(dataset_path)
    if validate:
        ok, errors = validate_dataset(data)
        if not ok:
            raise ValueError("Dataset validation failed:\n" + "\n".join(errors[:20]))
    if max_samples is not None and max_samples > 0:
        data = data[:max_samples]
    return data


def get_formatted_texts(
    data: List[Dict[str, Any]],
    prompt_template: Optional[str] = None,
) -> List[str]:
    """Return list of formatted prompt strings for SFT (one per example)."""
    return [format_prompt(ex, template=prompt_template) for ex in data]
