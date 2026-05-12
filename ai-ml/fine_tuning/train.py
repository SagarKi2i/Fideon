"""
QLoRA supervised fine-tuning for Qwen2-VL-7B.

run_training() is the public entry point called by job_runner.run_cycle().

Training backends
-----------------
1. LLaMA-Factory CLI  (preferred — set USE_LLAMA_FACTORY=1 or auto-detected)
   Writes dataset_info.json + lf_config.yaml, then shells out to:
       llamafactory-cli train <config>

2. HuggingFace Trainer / PEFT QLoRA  (fallback when LLaMA-Factory not found)

Training format
---------------
Chat-format JSONL with messages: [system, user, assistant].
Only the assistant turn is used as the training label (SFT).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use LLaMA-Factory when: env var is set to 1/true, OR the CLI is on PATH
# and USE_LLAMA_FACTORY is not explicitly disabled.
_LF_ENV = os.getenv("USE_LLAMA_FACTORY", "").strip().lower()
USE_LLAMA_FACTORY: bool = (
    _LF_ENV in {"1", "true", "yes"}
    or (
        _LF_ENV not in {"0", "false", "no"}
        and shutil.which("llamafactory-cli") is not None
    )
)


# ── Periodic logger ───────────────────────────────────────────────────────────

class _PeriodicLogger:
    """Prints a status line every `interval` seconds in a daemon thread.

    Use as a context manager:
        with _PeriodicLogger(10, lambda: f"Still loading... {elapsed}s"):
            blocking_call()
    """
    def __init__(self, interval: float, fn):
        self._interval = interval
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=self._interval + 1)

    def _run(self):
        while not self._stop.wait(self._interval):
            try:
                print(self._fn(), flush=True)
            except Exception:
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


# ── Dataset formatting ────────────────────────────────────────────────────────

def _build_qwen_chat(msgs: List[Dict[str, Any]]) -> str:
    """Manually construct Qwen ChatML string — reliable fallback for any tokenizer version."""
    parts = []
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            # Multimodal list-of-dicts → extract text parts only
            content = " ".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    return "\n".join(parts) + "\n"


def _format_chat_row(row: Dict[str, Any], tokenizer: Any) -> Optional[str]:
    """Apply Qwen2-VL chat template to one row, with manual fallback."""
    msgs = row.get("messages")
    if not isinstance(msgs, list):
        print(f"[train] Skipping row — 'messages' is {type(msgs).__name__}, not list. Keys: {list(row.keys())}")
        return None
    try:
        text = tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=False
        )
        if text:
            return text
        # apply_chat_template returned empty/None — use manual template
        print("[train] apply_chat_template returned empty — using manual Qwen ChatML template")
    except Exception as e:
        print(f"[train] apply_chat_template failed ({e}) — using manual Qwen ChatML template")
    try:
        return _build_qwen_chat(msgs)
    except Exception as e2:
        print(f"[train] Manual template also failed: {e2}. messages={msgs!r}")
        return None


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s:
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


# ── LLaMA-Factory backend ─────────────────────────────────────────────────────

def _dict_to_yaml(d: Dict[str, Any]) -> str:
    """Minimal dict→YAML serialiser for the scalar types used in lf_config."""
    lines: List[str] = []
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, str):
            # Quote strings that contain YAML special characters
            if any(c in v for c in ": #{}[]|>&*!,@`\"'\\") or not v:
                safe = v.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{k}: "{safe}"')
            else:
                lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"


def _run_llamafactory_training(
    config: Dict[str, Any],
    dataset_path: str,
    output_dir: str,
    job_id: str,
    base_model: str,
) -> str:
    """
    Invoke LLaMA-Factory CLI for QLoRA SFT.

    Expects the dataset directory to already contain:
        data/train.jsonl
        data/dataset_info.json
    (DatasetBuilder.build() writes this layout automatically.)

    Returns the adapter output directory path (same as output_dir).
    """
    lora_cfg  = config.get("lora", {})
    train_cfg = config.get("training", {})
    local_only = str(config.get("local_files_only", "true")).lower() in {"1", "true", "yes"}

    dataset_dir = Path(dataset_path).parent
    lf_data_dir = dataset_dir / "data"

    # If DatasetBuilder didn't create the data/ layout, create it now
    if not lf_data_dir.exists():
        lf_data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(dataset_path, lf_data_dir / "train.jsonl")
        _lf_info = {
            "fideon_insurance": {
                "file_name": "train.jsonl",
                "formatting": "sharegpt",
                "columns": {"messages": "messages"},
            }
        }
        (lf_data_dir / "dataset_info.json").write_text(
            json.dumps(_lf_info, indent=2), encoding="utf-8"
        )

    lf_config: Dict[str, Any] = {
        "model_name_or_path": base_model,
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "lora_rank": int(lora_cfg.get("r", 16)),
        "lora_alpha": float(lora_cfg.get("lora_alpha", 32)),
        "lora_dropout": float(lora_cfg.get("lora_dropout", 0.05)),
        "lora_target": "all",
        "visual_inputs": True,   # enable multimodal (Qwen2-VL)
        "dataset": "fideon_insurance",
        "dataset_dir": str(lf_data_dir),
        "template": "qwen2_vl",
        "cutoff_len": int(train_cfg.get("max_seq_length", 2048)),
        "overwrite_cache": True,
        "output_dir": str(output_dir),
        "logging_dir": str(Path(output_dir) / "logs"),
        "per_device_train_batch_size": int(train_cfg.get("per_device_train_batch_size", 1)),
        "gradient_accumulation_steps": int(train_cfg.get("gradient_accumulation_steps", 4)),
        "lr_scheduler_type": "cosine",
        "logging_steps": int(train_cfg.get("logging_steps", 5)),
        "warmup_ratio": float(train_cfg.get("warmup_ratio", 0.10)),
        "save_steps": 100,
        "overwrite_output_dir": True,
        "learning_rate": float(train_cfg.get("learning_rate", 2e-5)),
        "num_train_epochs": float(train_cfg.get("num_epochs", 3)),
        "pure_bf16": bool(train_cfg.get("bf16", True)),
        "plot_loss": False,
        "report_to": "none",
        "run_name": f"fideon-{job_id}",
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    config_path = Path(output_dir) / "lf_config.yaml"
    config_path.write_text(_dict_to_yaml(lf_config), encoding="utf-8")

    print(
        f"[train] ── LLaMA-Factory ── Starting: llamafactory-cli train {config_path}",
        flush=True,
    )
    result = subprocess.run(
        ["llamafactory-cli", "train", str(config_path)],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"[train] LLaMA-Factory exited with code {result.returncode}. "
            f"Check logs in {Path(output_dir) / 'logs'}."
        )

    print(
        f"[train] LLaMA-Factory training complete. Adapter at {output_dir}",
        flush=True,
    )
    return str(output_dir)


# ── Public entry point ────────────────────────────────────────────────────────

def run_training(
    config: Dict[str, Any],
    dataset_path: str,
    output_dir: str,
    job_id: str,
    base_model: str,
) -> str:
    """
    Run QLoRA fine-tuning on the chat-format JSONL at dataset_path.

    Delegates to LLaMA-Factory CLI when USE_LLAMA_FACTORY=1 or llamafactory-cli
    is on PATH; otherwise falls back to the built-in HF Trainer / PEFT path.

    Returns the adapter output directory path.
    """
    _use_lf = USE_LLAMA_FACTORY or str(config.get("use_llamafactory", "")).lower() in {"1", "true", "yes"}
    if _use_lf:
        print("[train] Backend: LLaMA-Factory CLI", flush=True)
        return _run_llamafactory_training(config, dataset_path, output_dir, job_id, base_model)

    print("[train] Backend: HuggingFace Trainer (PEFT QLoRA)", flush=True)
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    import torch
    from torch.nn.utils.rnn import pad_sequence
    from transformers import (
        AutoProcessor,
        BitsAndBytesConfig,
        Qwen2VLForConditionalGeneration,
        TrainingArguments,
        Trainer,
    )

    output_dir = str(output_dir)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    lora_cfg  = config.get("lora", {})
    train_cfg = config.get("training", {})
    local_only = str(config.get("local_files_only", "true")).lower() in {"1", "true", "yes"}

    # Free any VRAM left from the OCR/VLM extraction model before training
    print("[train] ── Phase 0/6 ── Clearing VRAM …", flush=True)
    try:
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[train]   VRAM cleared.", flush=True)
    except Exception:
        pass

    # ── Phase 1/6: Load processor ────────────────────────────────────────────
    _t0 = time.time()
    print(f"[train] ── Phase 1/6 ── Loading processor from {base_model} …", flush=True)
    with _PeriodicLogger(10, lambda: f"[train]   Still loading processor… ({int(time.time()-_t0)}s elapsed)"):
        try:
            processor = AutoProcessor.from_pretrained(
                base_model, local_files_only=local_only, fix_mistral_regex=True
            )
        except TypeError:
            processor = AutoProcessor.from_pretrained(base_model, local_files_only=local_only)
    tokenizer = processor.tokenizer
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print(f"[train]   Processor ready. ({int(time.time()-_t0)}s)", flush=True)

    # ── Phase 2/6: Load model in 4-bit QLoRA ────────────────────────────────
    _t0 = time.time()
    print(f"[train] ── Phase 2/6 ── Loading 4-bit quantized model (5 checkpoint shards, ~40-60s) …", flush=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    with _PeriodicLogger(10, lambda: f"[train]   Loading model shards… ({int(time.time()-_t0)}s elapsed)"):
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            base_model,
            quantization_config=bnb_config,
            device_map="auto",
            local_files_only=local_only,
        )
    print(f"[train]   Model loaded. ({int(time.time()-_t0)}s) Preparing for k-bit training…", flush=True)
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=bool(train_cfg.get("gradient_checkpointing", True)),
    )

    # ── Phase 3/6: Apply LoRA ────────────────────────────────────────────────
    print(
        f"[train] ── Phase 3/6 ── Applying LoRA adapters "
        f"(r={lora_cfg.get('r', 16)}, alpha={lora_cfg.get('lora_alpha', 32)}) …",
        flush=True,
    )
    target_modules = lora_cfg.get(
        "target_modules",
        ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    lora_config = LoraConfig(
        r=int(lora_cfg.get("r", 16)),
        lora_alpha=int(lora_cfg.get("lora_alpha", 32)),
        target_modules=target_modules,
        lora_dropout=float(lora_cfg.get("lora_dropout", 0.05)),
        bias=lora_cfg.get("bias", "none"),
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Phase 4/6: Load and format dataset ───────────────────────────────────
    print(f"[train] ── Phase 4/6 ── Loading dataset from {dataset_path} …", flush=True)
    rows = _load_jsonl(Path(dataset_path))
    max_seq = int(train_cfg.get("max_seq_length", 2048))

    texts = []
    for row in rows:
        t = _format_chat_row(row, tokenizer)
        if t:
            texts.append(t)

    # ── Phase 5/6: Tokenise ───────────────────────────────────────────────────
    print(f"[train] ── Phase 5/6 ── Tokenising {len(texts)} examples (max_seq={max_seq}) …", flush=True)
    if not texts:
        raise ValueError(
            f"[train] 0 examples after chat-template formatting. "
            f"Loaded {len(rows)} rows from {dataset_path}. "
            "Check that each row has a 'messages' list with valid role/content dicts."
        )

    # Qwen2-VL chat template wraps the assistant turn with <|im_start|>assistant\n
    # We mask all non-assistant tokens to -100 so the loss is only computed on
    # the model's actual outputs, not on the system prompt or user content.
    _ASSISTANT_PREFIX = "<|im_start|>assistant\n"

    def _tokenise(batch: Dict[str, Any]) -> Dict[str, Any]:
        input_ids_list, attention_mask_list, labels_list = [], [], []

        for text in batch["text"]:
            prefix_end = text.rfind(_ASSISTANT_PREFIX)
            if prefix_end != -1:
                prefix_text = text[: prefix_end + len(_ASSISTANT_PREFIX)]

                # Tokenize prefix and full text with IDENTICAL settings so the
                # split point is consistent. add_special_tokens=False because
                # the Qwen2 chat template already embeds all special markers
                # (<|im_start|>, <|im_end|>) as explicit text tokens.
                prefix_ids = tokenizer(
                    prefix_text,
                    add_special_tokens=False,
                    truncation=False,
                    padding=False,
                )["input_ids"]
                full_ids = tokenizer(
                    text,
                    add_special_tokens=False,
                    truncation=False,
                    padding=False,
                )["input_ids"]

                completion_ids = full_ids[len(prefix_ids):]

                # ── Truncate the PREFIX (never the completion) ──────────────
                # If we truncated from the end (original behaviour) the
                # assistant response would be cut off entirely, making every
                # label -100 → loss=0, grad_norm=0, model learns nothing.
                if len(prefix_ids) + len(completion_ids) > max_seq:
                    budget     = max(0, max_seq - len(completion_ids))
                    prefix_ids = prefix_ids[-budget:]   # keep most-recent context

                combined = prefix_ids + completion_ids
                labels   = [-100] * len(prefix_ids) + list(completion_ids)
            else:
                # No assistant boundary — train on full sequence (rare fallback).
                combined = tokenizer(
                    text,
                    add_special_tokens=False,
                    truncation=True,
                    max_length=max_seq,
                    padding=False,
                )["input_ids"]
                labels = list(combined)

            # Safety: if something went wrong and all labels are masked,
            # fall back to training on the whole sequence rather than silently
            # producing zero loss.
            if all(l == -100 for l in labels):
                labels = list(combined)

            input_ids_list.append(combined)
            attention_mask_list.append([1] * len(combined))
            labels_list.append(labels)

        return {
            "input_ids":      input_ids_list,
            "attention_mask": attention_mask_list,
            "labels":         labels_list,
        }

    hf_dataset = Dataset.from_dict({"text": texts})
    tokenised  = hf_dataset.map(_tokenise, batched=True, remove_columns=["text"])

    # ── Diagnostic: verify labels are not all masked ──────────────────────────
    active_counts = [sum(1 for l in ex["labels"] if l != -100) for ex in tokenised]
    seq_lengths   = [len(ex["input_ids"]) for ex in tokenised]
    _min_active = min(active_counts) if active_counts else 0
    _max_active = max(active_counts) if active_counts else 0
    _avg_active = sum(active_counts) // max(len(active_counts), 1)
    print(
        f"[train] Label check — {len(tokenised)} examples | "
        f"active label tokens: min={_min_active} max={_max_active} avg={_avg_active} | "
        f"seq len: min={min(seq_lengths)} max={max(seq_lengths)}",
        flush=True,
    )
    if _min_active == 0:
        # The safety fallback in _tokenise should have prevented this, but if it
        # still happens the assistant boundary was not found in ANY example —
        # something is fundamentally wrong with the JSONL format.
        raise ValueError(
            f"[train] FATAL: {sum(1 for c in active_counts if c == 0)} example(s) still have "
            f"0 active label tokens after the safety fallback. "
            f"The '<|im_start|>assistant\\n' boundary was not found in the chat template output. "
            f"Check that each JSONL row has a 'messages' list with an 'assistant' role entry. "
            f"Dataset: {dataset_path}"
        )

    # ── Train ────────────────────────────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=int(train_cfg.get("num_epochs", 3)),
        per_device_train_batch_size=int(train_cfg.get("per_device_train_batch_size", 1)),
        gradient_accumulation_steps=int(train_cfg.get("gradient_accumulation_steps", 4)),
        learning_rate=float(train_cfg.get("learning_rate", 2e-5)),
        weight_decay=float(train_cfg.get("weight_decay", 0.01)),
        max_grad_norm=float(train_cfg.get("max_grad_norm", 0.3)),
        fp16=False,
        bf16=bool(train_cfg.get("bf16", True)),
        gradient_checkpointing=bool(train_cfg.get("gradient_checkpointing", True)),
        warmup_ratio=float(train_cfg.get("warmup_ratio", 0.10)),
        logging_steps=int(train_cfg.get("logging_steps", 5)),
        save_strategy=train_cfg.get("save_strategy", "epoch"),
        save_total_limit=int(train_cfg.get("save_total_limit", 2)),
        optim=train_cfg.get("optim", "paged_adamw_8bit"),
        report_to="none",
        run_name=f"fideon-acord-{job_id}",
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )

    pad_id = tokenizer.pad_token_id

    def _collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Pad pre-tokenised examples, preserving the assistant-masked labels."""
        input_ids = pad_sequence(
            [torch.tensor(b["input_ids"], dtype=torch.long) for b in batch],
            batch_first=True, padding_value=pad_id,
        )
        attention_mask = pad_sequence(
            [torch.tensor(b["attention_mask"], dtype=torch.long) for b in batch],
            batch_first=True, padding_value=0,
        )
        labels = pad_sequence(
            [torch.tensor(b["labels"], dtype=torch.long) for b in batch],
            batch_first=True, padding_value=-100,
        )
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}

    from transformers import TrainerCallback

    class _ProgressCB(TrainerCallback):
        """Prints training progress every ~10 seconds."""
        def __init__(self):
            self._last = 0.0
            self._t0 = time.time()

        def on_step_end(self, args, state, control, **kwargs):
            now = time.time()
            if now - self._last < 10:
                return
            self._last = now
            total   = state.max_steps or 1
            elapsed = int(now - self._t0)
            pct     = state.global_step / total * 100
            loss_val = state.log_history[-1].get("loss") if state.log_history else None
            loss_str = f"{loss_val:.4f}" if isinstance(loss_val, float) else "—"
            eta_s    = int(elapsed / max(state.global_step, 1) * (total - state.global_step))
            print(
                f"[train] Training — step {state.global_step}/{total} ({pct:.0f}%)"
                f" | epoch {state.epoch:.1f} | loss={loss_str}"
                f" | elapsed={elapsed}s | ETA≈{eta_s}s",
                flush=True,
            )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenised,
        data_collator=_collate_fn,
        callbacks=[_ProgressCB()],
    )

    # ── Phase 6/6: Train ─────────────────────────────────────────────────────
    _t0_train = time.time()
    print(
        f"[train] ── Phase 6/6 ── Starting QLoRA training "
        f"({training_args.num_train_epochs} epochs, {len(tokenised)} examples) …",
        flush=True,
    )
    train_output = trainer.train()
    _final_loss = float(train_output.training_loss) if train_output is not None else 0.0
    print(
        f"[train]   Training complete. ({int(time.time()-_t0_train)}s) "
        f"final_loss={_final_loss:.6f}",
        flush=True,
    )

    adapter_path = output_dir
    print(f"[train] ── Saving ── Writing adapter weights to {adapter_path} …", flush=True)
    model.save_pretrained(adapter_path)
    processor.save_pretrained(adapter_path)

    # Write adapter manifest
    manifest = {
        "job_id": job_id,
        "base_model": base_model,
        "adapter_path": adapter_path,
        "dataset_path": dataset_path,
        "lora_r": lora_config.r,
        "lora_alpha": lora_config.lora_alpha,
        "num_epochs": training_args.num_train_epochs,
        "learning_rate": training_args.learning_rate,
        "train_loss": _final_loss,
        "min_active_labels": _min_active,
        "max_active_labels": _max_active,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    (Path(adapter_path) / "adapter_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"[train] All done. Adapter saved to {adapter_path}.", flush=True)
    return adapter_path
