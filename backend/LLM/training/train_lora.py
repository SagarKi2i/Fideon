"""
Entry point for LoRA / QLoRA fine‑tuning of the base LLaMA model.

This script is intended to be launched via `accelerate launch train_lora.py`
and parameterized by a YAML config in `../configs/train_config.yaml`.
"""


def main() -> None:
    """
    Placeholder for training loop.

    The final implementation should:
    - load training config
    - prepare dataset(s)
    - configure PEFT / LoRA
    - run SFT training
    - log metrics to MLflow / W&B
    - register adapters in the model registry
    """
    raise NotImplementedError("LoRA training script not implemented yet.")


if __name__ == "__main__":
    main()

