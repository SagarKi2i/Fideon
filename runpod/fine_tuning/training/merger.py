"""
AdapterMerger — merge a LoRA adapter into the base model weights.

Uses peft.PeftModel.merge_and_unload() to produce a standalone full-weight
model that can be loaded without PEFT at inference time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class MergeResult:
    output_path: str
    cycle_id: str
    version: int
    merged_at: str
    base_model_path: str
    adapter_path: str


class AdapterMerger:
    def merge(
        self,
        adapter_path: str,
        base_model_path: str,
        output_path: str,
        config: Dict[str, Any],
        cycle_id: str,
        version: int,
    ) -> MergeResult:
        """
        Load base model + LoRA adapter, call merge_and_unload(), save merged weights.

        Parameters
        ----------
        adapter_path    : directory containing PEFT adapter_config.json + weights
        base_model_path : original base model (Qwen2-VL-7B)
        output_path     : destination for the merged full-weight model
        config          : pipeline config dict
        cycle_id        : current training cycle ID
        version         : new version number (int)
        """
        import torch
        from peft import PeftModel
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

        adapter_path = str(adapter_path)
        base_model_path = str(base_model_path)
        output_path = str(output_path)

        Path(output_path).mkdir(parents=True, exist_ok=True)

        print(f"[merger] Loading base model from {base_model_path} …")
        local_only = str(config.get("local_files_only", "true")).lower() in {
            "1", "true", "yes",
        }
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        base_model = Qwen2VLForConditionalGeneration.from_pretrained(
            base_model_path,
            dtype=dtype,
            device_map="auto",         # use GPU when available (H100 80GB has headroom)
            local_files_only=local_only,
        )
        processor = AutoProcessor.from_pretrained(
            base_model_path, local_files_only=local_only
        )

        print(f"[merger] Attaching LoRA adapter from {adapter_path} …")
        peft_model = PeftModel.from_pretrained(base_model, adapter_path)

        print("[merger] Merging and unloading LoRA weights …")
        merged = peft_model.merge_and_unload()

        print(f"[merger] Saving merged model to {output_path} …")
        merged.save_pretrained(output_path)
        processor.save_pretrained(output_path)

        merged_at = datetime.now(timezone.utc).isoformat()
        manifest = {
            "version": version,
            "cycle_id": cycle_id,
            "base_model_path": base_model_path,
            "adapter_path": adapter_path,
            "output_path": output_path,
            "merged_at": merged_at,
        }
        (Path(output_path) / "merge_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print("[merger] Done.")

        return MergeResult(
            output_path=output_path,
            cycle_id=cycle_id,
            version=version,
            merged_at=merged_at,
            base_model_path=base_model_path,
            adapter_path=adapter_path,
        )
