"""Write a MODEL_CARD.md to the merged model directory after promotion."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def write_model_card(merged_model_path: str, meta: Dict[str, Any]) -> Path:
    """
    Write MODEL_CARD.md to merged_model_path/.

    meta keys (all optional):
      version, cycle_id, job_id, base_model, eval_scores, training_meta, promoted_at
    """
    dest = Path(merged_model_path) / "MODEL_CARD.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    version     = meta.get("version", "?")
    cycle_id    = meta.get("cycle_id", "?")
    base_model  = meta.get("base_model", "Qwen2-VL-7B")
    eval_scores = meta.get("eval_scores") or {}
    training    = meta.get("training_meta") or {}
    promoted_at = meta.get("promoted_at") or datetime.now(timezone.utc).isoformat()

    scores_lines = "\n".join(
        f"| {k} | {v} |" for k, v in eval_scores.items()
    ) or "| — | — |"

    card = f"""# Fideon SLM v1.{version} — ACORD Field Extraction

**Base model**: `{base_model}`
**Fine-tuned version**: v1.{version} (cycle `{cycle_id}`)
**Promoted at**: {promoted_at}
**Training backend**: QLoRA (bitsandbytes 4-bit + PEFT LoRA)

## Evaluation Scores

| Metric | Score |
|--------|-------|
{scores_lines}

## Training Config

```json
{__import__('json').dumps(training, indent=2)}
```

## Usage

This model is loaded automatically by the Fideon RunPod extraction server
when `resolve_base_model_path()` returns this directory.

```python
from transformers import AutoProcessor
from peft import PeftModel, PeftConfig
import torch

config    = PeftConfig.from_pretrained("{merged_model_path}")
processor = AutoProcessor.from_pretrained(config.base_model_name_or_path)
model     = PeftModel.from_pretrained(config.base_model_name_or_path, "{merged_model_path}")
```
"""
    dest.write_text(card, encoding="utf-8")
    return dest
