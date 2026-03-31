from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
    TrainingArguments,
)
from trl import SFTTrainer

logger = logging.getLogger("acord125.train")


class LossLogger(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        if not logs:
            return
        if "loss" in logs:
            logger.info("step=%s loss=%.6f", state.global_step, float(logs["loss"]))


def _format_chat(example: Dict[str, Any], tokenizer) -> Dict[str, str]:
    msgs = example["messages"]
    text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    return {"text": text}


def _token_accuracy(model, tokenizer, ds, max_samples: int = 16) -> float:
    """
    Lightweight token-level accuracy over a small sample.
    """
    model.eval()
    n, correct = 0, 0
    for i in range(min(len(ds), max_samples)):
        sample = ds[i]["text"]
        toks = tokenizer(sample, return_tensors="pt", truncation=True, max_length=4096).to(model.device)
        with torch.no_grad():
            out = model(**toks)
        logits = out.logits[:, :-1, :]
        labels = toks["input_ids"][:, 1:]
        pred = logits.argmax(dim=-1)
        mask = labels.ne(-100)
        correct += int((pred.eq(labels) & mask).sum().item())
        n += int(mask.sum().item())
    return float(correct / n) if n else 0.0


def train(
    dataset_path: Path,
    base_model: str,
    output_dir: Path,
    epochs: int = 2,
    learning_rate: float = 2e-5,
    batch_size: int = 1,
    grad_accum: int = 8,
) -> None:
    raw = load_dataset("json", data_files=str(dataset_path), split="train")
    if len(raw) <= 100:
        raise RuntimeError(f"Dataset too small ({len(raw)} samples). Need > 100 samples to avoid overfitting.")

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    ds = raw.map(lambda ex: _format_chat(ex, tokenizer), remove_columns=raw.column_names)

    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_cfg,
        device_map="auto",
        trust_remote_code=True,
    )
    model.gradient_checkpointing_enable()

    lora_cfg = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        fp16=False,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=ds,
        args=args,
        dataset_text_field="text",
        tokenizer=tokenizer,
        max_seq_length=4096,
        packing=True,
        callbacks=[LossLogger()],
    )
    trainer.train()
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    token_acc = _token_accuracy(model, tokenizer, ds)
    logger.info("token_accuracy=%.4f", token_acc)
    (output_dir / "train_metrics.json").write_text(
        json.dumps({"token_accuracy": token_acc, "train_samples": len(ds)}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description="QLoRA training for ACORD 125 chat JSON extraction.")
    parser.add_argument("--dataset", required=True, help="Path to acord_dataset.jsonl (chat messages format)")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-14B-Instruct")
    parser.add_argument("--output-dir", default="fine_tuning/runs/acord125_adapter")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    args = parser.parse_args()
    train(
        dataset_path=Path(args.dataset),
        base_model=args.base_model,
        output_dir=Path(args.output_dir),
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
    )


if __name__ == "__main__":
    main()

