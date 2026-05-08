"""
Load base causal LM + LoRA adapter for inference (e.g. evaluation or API).

Usage:
  from fine_tuning.inference import load_model_for_inference
  model, tokenizer = load_model_for_inference("Qwen/Qwen2.5-14B-Instruct", "qwen_lora_adapter")
  reply = generate(model, tokenizer, "What is ACORD Form 125?")
"""

import os
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from .data import format_prompt_for_inference


def _get_hf_token(use_auth: Any) -> Optional[str]:
    if use_auth is None or use_auth is False:
        return None
    if isinstance(use_auth, str) and use_auth.strip():
        return use_auth.strip()
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token
    try:
        from huggingface_hub import get_token
        return get_token()
    except Exception:
        return None


def _flash_attn_kwargs() -> dict:
    """Return attn_implementation='flash_attention_2' if the package is available."""
    try:
        import flash_attn  # noqa: F401
        return {"attn_implementation": "flash_attention_2"}
    except ImportError:
        return {}


def load_base_model_only(
    base_model: str,
    *,
    load_in_4bit: bool = True,
    use_auth_token: Any = False,
    local_files_only: bool = False,
) -> Tuple[Any, Any]:
    """Load base model only (no LoRA). Returns (model, tokenizer)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    token = _get_hf_token(use_auth_token)
    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        token=token,
        local_files_only=local_files_only,
    )
    extra = _flash_attn_kwargs()
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        import torch
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
            ),
            device_map="auto",
            trust_remote_code=True,
            token=token,
            local_files_only=local_files_only,
            **extra,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            device_map="auto",
            trust_remote_code=True,
            token=token,
            local_files_only=local_files_only,
            **extra,
        )
    model.eval()
    return model, tokenizer


def load_model_for_inference(
    base_model: str,
    adapter_path: Union[str, Path],
    *,
    load_in_4bit: bool = True,
    use_auth_token: Any = False,
    local_files_only: bool = False,
) -> Tuple[Any, Any]:
    """
    Load base model and merge LoRA adapter. Returns (model, tokenizer).
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    token = _get_hf_token(use_auth_token)
    tokenizer = AutoTokenizer.from_pretrained(
        adapter_path,
        trust_remote_code=True,
        token=token,
        local_files_only=local_files_only,
    )
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        import torch
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
            ),
            device_map="auto",
            trust_remote_code=True,
            token=token,
            local_files_only=local_files_only,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            device_map="auto",
            trust_remote_code=True,
            token=token,
            local_files_only=local_files_only,
        )
    model = PeftModel.from_pretrained(model, str(adapter_path))
    model.eval()
    return model, tokenizer


def generate(
    model: Any,
    tokenizer: Any,
    instruction: str,
    input_text: str = "",
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    do_sample: bool = True,
) -> str:
    """Run one instruction and return the generated response text."""
    prompt = format_prompt_for_inference(instruction, input_text)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with __import__("torch").no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=do_sample,
            pad_token_id=tokenizer.eos_token_id,
        )
    # Decode only the new part
    gen = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def generate_from_raw_prompt(
    model: Any,
    tokenizer: Any,
    prompt: str,
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.0,
) -> str:
    """
    Generate from an already-formatted prompt.

    For chat-tuned models (e.g. Qwen2.5-14B-Instruct, Llama-3-Instruct) the
    prompt is sent as the user turn of a chat conversation so the model's chat
    template is respected.  A hard system message reinforces JSON-only output.
    Falls back to raw tokenisation if the tokenizer has no chat template.
    """
    # --- Apply chat template when the tokenizer supports it ---
    formatted: str = prompt
    if getattr(tokenizer, "chat_template", None):
        _SYS = (
            "You are a precise data extraction engine. "
            "Your output must be ONLY valid JSON — no markdown fences, "
            "no commentary, no leading or trailing text."
        )
        messages = [
            {"role": "system", "content": _SYS},
            {"role": "user", "content": prompt},
        ]
        try:
            formatted = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            formatted = prompt

    inputs = tokenizer(formatted, return_tensors="pt").to(model.device)
    do_sample = temperature > 0.0
    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
    with __import__("torch").no_grad():
        out = model.generate(**inputs, **gen_kwargs)
    generated = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


# Default verification prompt (Step 9 in workflow: reduce hallucination)
VERIFICATION_PROMPT = (
    "Check whether the following answer is fully supported by the document. "
    "If unsupported claims exist, correct the answer. Otherwise repeat the answer as-is.\n\n"
    "Question: {instruction}\n\nAnswer to verify: {answer}\n\nCorrected or confirmed answer:"
)


def generate_with_verification(
    model: Any,
    tokenizer: Any,
    instruction: str,
    input_text: str = "",
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    verification_prompt: Optional[str] = None,
    max_verification_tokens: int = 150,
) -> str:
    """
    Generate answer, then optionally run a verification pass to reduce hallucination.
    If verification_prompt is None, behaves like generate().
    """
    answer = generate(
        model, tokenizer, instruction, input_text,
        max_new_tokens=max_new_tokens, temperature=temperature, do_sample=temperature > 0,
    )
    if not verification_prompt:
        return answer
    verify_inst = (verification_prompt or VERIFICATION_PROMPT).format(
        instruction=instruction, answer=answer,
    )
    verified = generate(
        model, tokenizer, verify_inst, "",
        max_new_tokens=max_verification_tokens, temperature=0.3, do_sample=False,
    )
    return verified.strip() if verified.strip() else answer
