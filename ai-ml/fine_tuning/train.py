"""
QLoRA supervised fine-tuning for Qwen2-VL-7B (text-only task).

run_training() is the public entry point called by job_runner.run_cycle().

Training format
---------------
Chat-format JSONL with messages: [system, user, assistant].
The processor applies the Qwen2-VL chat template to produce token sequences.
Only the assistant turn is used as the training label (SFT).
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    Returns the adapter output directory path.
    """
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
        enc = tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_seq,
            padding=False,
        )
        labels_list = []
        for text, input_ids in zip(batch["text"], enc["input_ids"]):
            labels = [-100] * len(input_ids)
            # Find where the last (assistant) turn begins and unmask from there
            prefix_end = text.rfind(_ASSISTANT_PREFIX)
            if prefix_end != -1:
                prefix_text = text[: prefix_end + len(_ASSISTANT_PREFIX)]
                prefix_len = len(
                    tokenizer(prefix_text, add_special_tokens=False)["input_ids"]
                )
                for i in range(prefix_len, len(input_ids)):
                    labels[i] = input_ids[i]
            else:
                # Fallback: train on full sequence if template boundary not found
                labels = input_ids[:]
            labels_list.append(labels)
        enc["labels"] = labels_list
        return enc

    hf_dataset = Dataset.from_dict({"text": texts})
    tokenised  = hf_dataset.map(_tokenise, batched=True, remove_columns=["text"])

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
    trainer.train()
    print(f"[train]   Training complete. ({int(time.time()-_t0_train)}s)", flush=True)

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
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    (Path(adapter_path) / "adapter_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"[train] All done. Adapter saved to {adapter_path}.", flush=True)
    return adapter_path
