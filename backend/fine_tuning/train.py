"""
QLoRA training for LLaMA 8B: 4-bit base + LoRA adapters.

Run with:
  accelerate launch fine_tuning/train.py --config fine_tuning/config.yaml
  python -m fine_tuning.train --config fine_tuning/config.yaml
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from .schema import validate_dataset


def _get_hf_token(use_auth: Any) -> Optional[str]:
    """Resolve Hugging Face token for gated repos. use_auth: True, False, or token string."""
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


_ENV_REF_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _coerce_scalar(value: Any) -> Any:
    """Coerce common env-substituted scalar strings to native types."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    low = s.lower()
    if low in {"true", "false"}:
        return low == "true"
    # Keep numeric coercion conservative; only plain ints/floats.
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except Exception:
            return value
    if re.fullmatch(r"-?\d+\.\d+", s):
        try:
            return float(s)
        except Exception:
            return value
    return value


def _resolve_env_refs(value: Any) -> Any:
    """Resolve ${VAR} / ${VAR:-default} recursively in config values."""
    if isinstance(value, dict):
        return {k: _resolve_env_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_refs(v) for v in value]
    if not isinstance(value, str):
        return value

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1)
        default = m.group(2) or ""
        return os.getenv(name, default)

    resolved = _ENV_REF_RE.sub(_sub, value)
    return _coerce_scalar(resolved)


def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Load YAML config and resolve env placeholders."""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_env_refs(raw)


def get_training_args(config: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """Build HuggingFace TrainingArguments from config."""
    t = config.get("training", {})
    args: Dict[str, Any] = {
        "output_dir": output_dir,
        "num_train_epochs": t.get("num_epochs", 3),
        "per_device_train_batch_size": t.get("per_device_train_batch_size", 2),
        "gradient_accumulation_steps": t.get("gradient_accumulation_steps", 4),
        "learning_rate": float(t.get("learning_rate", 2e-4)),
        "weight_decay": float(t.get("weight_decay", 0.0)),
        "fp16": t.get("fp16", False),
        "bf16": t.get("bf16", True),
        "gradient_checkpointing": t.get("gradient_checkpointing", True),
        "warmup_ratio": t.get("warmup_ratio", 0.03),
        "logging_steps": t.get("logging_steps", 10),
        "save_strategy": t.get("save_strategy", "steps"),
        "save_steps": t.get("save_steps", 100),
        "save_total_limit": t.get("save_total_limit", 2),
        "optim": t.get("optim", "paged_adamw_8bit"),
        "report_to": "none",
    }
    if t.get("max_grad_norm") is not None:
        args["max_grad_norm"] = float(t["max_grad_norm"])
    return args


def run_training(
    config_path: Union[str, Path],
    dataset_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> str:
    """
    Load config, prepare dataset, apply QLoRA, train, save adapter.
    Returns path to saved adapter directory.
    """
    config = load_config(config_path)
    if dataset_path is None:
        dataset_path = config.get("dataset_path", "dataset.json")
    if output_dir is None:
        output_dir = config.get("output_dir", "llama_lora_adapter")
    output_dir = str(Path(output_dir).resolve())
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Optional: load from datasets library for SFTTrainer
    try:
        from datasets import Dataset, load_dataset
    except ImportError:
        raise ImportError("Install: pip install datasets")

    data_path = Path(dataset_path)
    if not data_path.is_absolute():
        base = Path(config_path).resolve().parent
        data_path = base / data_path
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_path}")

    # Optional: validate dataset schema before training.
    # Use shared loader so JSON and JSONL both work robustly.
    from .data import load_dataset_json
    data_list = load_dataset_json(data_path)
    ok, errors = validate_dataset(
        data_list,
        require_json_output=bool(config.get("require_json_output", False)),
    )
    if not ok:
        raise ValueError("Dataset validation failed:\n" + "\n".join(errors[:15]))

    # Load JSON/JSONL into HuggingFace Dataset
    if str(data_path).endswith(".jsonl"):
        dataset = load_dataset("json", data_files=str(data_path), split="train")
    else:
        dataset = load_dataset("json", data_files=str(data_path), split="train")

    max_train = config.get("max_train_samples")
    if max_train is not None and max_train > 0:
        dataset = dataset.select(range(min(max_train, len(dataset))))

    tconf = config.get("training") or {}
    eval_cfg = config.get("evaluation") or {}
    env_es = os.getenv("ACORD_EXPORT_EVAL_SPLIT_RATIO")
    if env_es is not None and str(env_es).strip() != "":
        eval_split_f = float(env_es)
    else:
        eval_split_f = float(eval_cfg.get("eval_split_ratio") or 0.0)

    def _legacy_acord_chat_auto(ds) -> bool:
        explicit = config.get("use_acord_chat_template")
        if explicit is True:
            return True
        if explicit is False:
            return False
        env_raw = (os.getenv("FINE_TUNE_ACORD_CHAT_TEMPLATE") or "").strip().lower()
        if env_raw in {"1", "true", "yes", "on"}:
            return True
        if env_raw in {"0", "false", "no", "off"}:
            return False
        if len(ds) == 0:
            return False
        for i in range(len(ds)):
            if ds[i].get("domain") not in (None, "", "insurance/acord"):
                return False
        return True

    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = config.get("base_model", "Qwen/Qwen2.5-14B-Instruct")
    use_auth = config.get("use_auth_token", True)
    hf_token = _get_hf_token(use_auth)
    local_files_only = bool(config.get("local_files_only", False))
    if use_auth and not hf_token:
        raise RuntimeError(
            "Gated or private base model requires Hugging Face auth. Run: huggingface-cli login "
            "and accept the model license on Hugging Face, or set HF_TOKEN / HUGGING_FACE_HUB_TOKEN."
        )
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, token=hf_token, local_files_only=local_files_only
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    use_legacy_acord_chat = _legacy_acord_chat_auto(dataset)
    from .data import format_acord_chat_sft, format_oos_chat_sft, format_prompt

    def format_fn(ex):
        dom = (ex.get("domain") or "").strip()
        if dom == "insurance/acord_oos":
            return {"text": format_oos_chat_sft(tokenizer, ex)}
        if dom == "insurance/acord":
            return {"text": format_acord_chat_sft(tokenizer, ex)}
        if use_legacy_acord_chat:
            return {"text": format_acord_chat_sft(tokenizer, ex)}
        return {"text": format_prompt(ex)}

    dataset = dataset.map(format_fn, remove_columns=dataset.column_names, num_proc=1)

    eval_dataset = None
    if eval_split_f > 0 and len(dataset) >= 20:
        sp = dataset.train_test_split(test_size=eval_split_f, seed=42)
        dataset = sp["train"]
        eval_dataset = sp["test"]
        print(f"[train] eval_split={len(eval_dataset)} early_stopping=true", flush=True)
    else:
        if eval_split_f > 0 and len(dataset) < 20:
            print("[train] eval_split=disabled (too few rows)", flush=True)
        else:
            print("[train] eval_split=disabled", flush=True)

    load_in_4bit = config.get("load_in_4bit", True)
    compute_dtype = config.get("bnb_4bit_compute_dtype", "bfloat16")
    quant_type = config.get("bnb_4bit_quant_type", "nf4")

    import torch
    # Preflight for production jobs: fail fast with actionable errors.
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Fine-tuning requires a GPU-enabled environment.")
    if load_in_4bit:
        try:
            import bitsandbytes  # noqa: F401
        except Exception as exc:
            raise RuntimeError("4-bit training requested but bitsandbytes is unavailable.") from exc

    dtype = torch.bfloat16 if compute_dtype == "bfloat16" else torch.float16
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_quant_type=quant_type,
                bnb_4bit_use_double_quant=True,
            ),
            device_map="auto",
            trust_remote_code=True,
            token=hf_token,
            local_files_only=local_files_only,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            trust_remote_code=True,
            token=hf_token,
            local_files_only=local_files_only,
        )

    # LoRA
    from peft import LoraConfig, PeftModel, get_peft_model

    lora_cfg = config.get("lora", {})
    lora_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("lora_alpha", 32),
        target_modules=lora_cfg.get("target_modules", ["q_proj", "v_proj"]),
        lora_dropout=lora_cfg.get("lora_dropout", 0.05),
        bias=lora_cfg.get("bias", "none"),
        task_type=lora_cfg.get("task_type", "CAUSAL_LM"),
    )
    model = get_peft_model(model, lora_config)

    # Optional continual fine-tuning: resume from previous adapter version.
    # This enables v1 -> v2 -> v3 style incremental updates instead of always
    # restarting adaptation from scratch.
    resume_adapter = str(
        config.get("resume_adapter_path")
        or os.getenv("FINE_TUNE_RESUME_ADAPTER", "")
    ).strip()
    if resume_adapter:
        resume_path = Path(resume_adapter).resolve()
        if not resume_path.exists():
            raise RuntimeError(f"FINE_TUNE_RESUME_ADAPTER does not exist: {resume_path}")
        model = PeftModel.from_pretrained(model, str(resume_path), is_trainable=True)

    # Training
    import inspect

    from trl import SFTTrainer
    from transformers import TrainingArguments

    max_seq_length = config.get("training", {}).get("max_seq_length", 2048)
    sft_params = set(inspect.signature(SFTTrainer.__init__).parameters.keys())
    if eval_dataset is not None and "eval_dataset" not in sft_params:
        eval_dataset = None

    training_args_dict = get_training_args(config, output_dir)
    if eval_dataset is not None:
        # load_best_model_at_end requires save_strategy and eval_strategy to match (both "steps").
        eval_steps = max(1, int(eval_cfg.get("eval_steps", 10)))
        training_args_dict["eval_strategy"] = "steps"
        training_args_dict["eval_steps"] = eval_steps
        training_args_dict["save_strategy"] = "steps"
        training_args_dict["save_steps"] = eval_steps
        training_args_dict["load_best_model_at_end"] = True
        training_args_dict["metric_for_best_model"] = "eval_loss"
        training_args_dict["greater_is_better"] = False
    training_args = TrainingArguments(**training_args_dict)

    # TRL API changed across versions (e.g., tokenizer -> processing_class).
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": dataset,
    }
    if "dataset_text_field" in sft_params:
        trainer_kwargs["dataset_text_field"] = "text"
    if "packing" in sft_params:
        trainer_kwargs["packing"] = False
    if "tokenizer" in sft_params:
        trainer_kwargs["tokenizer"] = tokenizer
    elif "processing_class" in sft_params:
        trainer_kwargs["processing_class"] = tokenizer
    if "max_seq_length" in sft_params:
        trainer_kwargs["max_seq_length"] = max_seq_length
    if eval_dataset is not None:
        if "eval_dataset" in sft_params:
            trainer_kwargs["eval_dataset"] = eval_dataset
    if eval_dataset is not None:
        try:
            from transformers import EarlyStoppingCallback

            trainer_kwargs["callbacks"] = [
                EarlyStoppingCallback(
                    early_stopping_patience=int(eval_cfg.get("early_stopping_patience", 3))
                )
            ]
        except Exception:
            pass

    try:
        trainer = SFTTrainer(**trainer_kwargs)
    except TypeError:
        # Last-resort fallback for older/newer TRL variants with stricter signatures.
        minimal_kwargs = {
            "model": model,
            "args": training_args,
            "train_dataset": dataset,
        }
        if "tokenizer" in sft_params:
            minimal_kwargs["tokenizer"] = tokenizer
        elif "processing_class" in sft_params:
            minimal_kwargs["processing_class"] = tokenizer
        if eval_dataset is not None and "eval_dataset" in sft_params:
            minimal_kwargs["eval_dataset"] = eval_dataset
        if "callbacks" in trainer_kwargs:
            minimal_kwargs["callbacks"] = trainer_kwargs["callbacks"]
        trainer = SFTTrainer(**minimal_kwargs)
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    return output_dir


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="fine_tuning/config.yaml")
    p.add_argument("--dataset", default=None)
    p.add_argument("--output-dir", default=None)
    a = p.parse_args()
    run_training(a.config, dataset_path=a.dataset, output_dir=a.output_dir)
