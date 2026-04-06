from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from trl import SFTTrainer

logger = logging.getLogger("acord.multiform.train")


def _format_chat(example: Dict[str, Any], tokenizer) -> Dict[str, str]:
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)}


def train_multiform(dataset_path: Path, base_model: str, output_dir: Path) -> None:
    if "synth" in dataset_path.name.lower() or "synthetic" in dataset_path.name.lower():
        raise RuntimeError(
            f"Synthetic dataset is disallowed: {dataset_path}. "
            "Use only real OCR-extracted, human-validated records."
        )
    ds = load_dataset("json", data_files=str(dataset_path), split="train")
    for i in range(min(len(ds), 512)):
        row = ds[i]
        source = str(row.get("data_source", "real")).strip().lower() if isinstance(row, dict) else "real"
        if source in {"synthetic", "synth", "generated", "fake"}:
            raise RuntimeError(
                f"Synthetic sample detected at row={i}; training aborted. "
                "Only real extracted fields are allowed."
            )
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    form_counts = Counter(ds["form_type"]) if "form_type" in ds.column_names else Counter()
    logger.info("per_form_training_distribution=%s", dict(form_counts))

    ds = ds.map(lambda ex: _format_chat(ex, tokenizer), remove_columns=ds.column_names)

    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(base_model, quantization_config=quant_cfg, device_map="auto", trust_remote_code=True)
    model.gradient_checkpointing_enable()

    lora_cfg = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "v_proj"], bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora_cfg)

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=2,
        learning_rate=2e-5,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        bf16=torch.cuda.is_available(),
        fp16=False,
        logging_steps=10,
        save_strategy="epoch",
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
    )
    trainer.train()
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    (output_dir / "per_form_distribution.json").write_text(json.dumps(dict(form_counts), indent=2), encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    p = argparse.ArgumentParser(description="Train multi-form ACORD model with QLoRA.")
    p.add_argument("--dataset", required=True, help="acord_multiform_dataset.jsonl")
    p.add_argument("--base-model", default="Qwen/Qwen2.5-14B-Instruct")
    p.add_argument("--output-dir", default="fine_tuning/runs/acord_multiform_adapter")
    args = p.parse_args()
    train_multiform(Path(args.dataset), args.base_model, Path(args.output_dir))


if __name__ == "__main__":
    main()

