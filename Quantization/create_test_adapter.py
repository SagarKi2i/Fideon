"""
Create a tiny LoRA adapter for TinyLlama — no GPU or real training data needed.
Does exactly 1 gradient step on a synthetic sentence so the adapter weights are
non-zero and the full quantization pipeline (merge → GGUF → quantize) works.

Usage:
    python create_test_adapter.py
    python create_test_adapter.py --output-dir /workspace/test_adapter

Output: a PEFT adapter directory that can be set as ADAPTER_PATH in config.env.local
"""

import argparse
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType

# ──────────────────────────────────────────────────────────────
# Config — use the same base model as config.env.local
# ──────────────────────────────────────────────────────────────
MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# LoRA targets that exist in TinyLlama (LlamaAttention)
LORA_TARGET_MODULES = ["q_proj", "v_proj"]

# Synthetic fine-tune sentence — domain: insurance underwriting
TRAINING_TEXT = (
    "Underwriting risk assessment requires evaluating policy applicant profiles, "
    "calculating premium rates, and determining coverage eligibility based on "
    "actuarial data and historical claims patterns."
)


def main(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    print(f"[1/4] Loading tokenizer from {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[2/4] Loading model (float32, CPU)...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float32,  # float32 is CPU-safe
        device_map="cpu",
    )

    print("[3/4] Attaching LoRA adapter (r=8, alpha=16)...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
        inference_mode=False,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print("[4/4] Running 1 training step on synthetic text...")
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    inputs = tokenizer(TRAINING_TEXT, return_tensors="pt")
    inputs["labels"] = inputs["input_ids"].clone()

    outputs = model(**inputs)
    loss = outputs.loss
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()

    print(f"      Training loss: {loss.item():.4f}  (non-zero = adapter weights are real)")

    # Save only the LoRA adapter — NOT the full merged model
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    adapter_files = os.listdir(output_dir)
    print(f"\n✓ Adapter saved to: {output_dir}")
    print(f"  Files: {adapter_files}")
    print(f"\nNext step: set ADAPTER_PATH={output_dir} in config.env.local")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a test LoRA adapter for TinyLlama")
    parser.add_argument(
        "--output-dir",
        default="./test_adapter",
        help="Directory to save the adapter (default: ./test_adapter)",
    )
    args = parser.parse_args()
    main(args.output_dir)
