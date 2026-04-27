"""
Training orchestrator — top-level promote_adapter() called after run_cycle().

Responsibilities (in order):
  1. Upload merged HF model   → SeaweedFS finetuned/v{N}/
  2. Quantize merged model    → GGUF Q5_K_M + Q4_K_M
  3. Upload quantized GGUFs   → SeaweedFS quantized/v{N}/
  4. Update version_registry.json with all SeaweedFS paths
  5. Write model card
  6. Send promotion alert
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fine_tuning.seaweedfs_client import SeaweedFSClient
from fine_tuning.observability.alerting import alerter


def promote_adapter(
    adapter_id: str,
    registry_path: str,
    version: int,
    merged_model_path: str,
    adapter_path: str,
    eval_scores: Dict[str, Any],
    training_meta: Dict[str, Any],
    base_model: str = "",
    actor: str = "pipeline",
    force: bool = False,
) -> Dict[str, Any]:
    """
    Finalise promotion of a merged model version.

    Steps
    -----
    1. Upload merged HF model   → SeaweedFS  finetuned/v{version}/
    2. Quantize                 → GGUF Q5_K_M + Q4_K_M (skipped if llama.cpp absent)
    3. Upload quantized GGUFs   → SeaweedFS  quantized/v{version}/
    4. Update registry          → promote_version() with all SeaweedFS paths
    5. Write model card
    6. Send alert
    """
    from fine_tuning.registry.version_registry import VersionRegistry
    from fine_tuning.registry.model_card import write_model_card
    from fine_tuning.quantization.quantizer import run_quantization

    registry = VersionRegistry(registry_path)
    seaweed  = SeaweedFSClient()

    seaweedfs_finetuned_prefix: Optional[str] = None
    seaweedfs_quantized_keys:   List[str]     = []

    # ── 1. Upload merged HF model → finetuned/v{N}/ ─────────────────────────
    print(f"[orchestrator] Uploading merged HF model (v{version}) to SeaweedFS …")
    try:
        seaweedfs_finetuned_prefix = seaweed.upload_hf_model(merged_model_path, version)
    except Exception as exc:
        print(f"[orchestrator] HF model upload failed (non-fatal): {exc}")

    # ── 2. Quantize merged model → GGUF ─────────────────────────────────────
    gguf_output_dir = str(Path(merged_model_path).parent / f"{version}-gguf")
    print(f"[orchestrator] Running quantization → {gguf_output_dir}")
    try:
        quant_results = run_quantization(merged_model_path, gguf_output_dir, version)
    except Exception as exc:
        print(f"[orchestrator] Quantization failed (non-fatal): {exc}")
        quant_results = {}

    # ── 3. Upload quantized GGUFs → quantized/v{N}/ ─────────────────────────
    if quant_results:
        print(f"[orchestrator] Uploading {len(quant_results)} GGUF(s) to SeaweedFS …")
        try:
            seaweedfs_quantized_keys = seaweed.upload_quantized(gguf_output_dir, version)
        except Exception as exc:
            print(f"[orchestrator] Quantized upload failed (non-fatal): {exc}")
    else:
        print("[orchestrator] No GGUF artifacts — skipping quantized upload.")

    # ── 4. Update registry ───────────────────────────────────────────────────
    registry.promote_version(
        version=version,
        merged_model_path=merged_model_path,
        adapter_path=adapter_path,
        eval_scores=eval_scores,
        training_meta={
            **training_meta,
            "seaweedfs_finetuned_prefix": seaweedfs_finetuned_prefix,
            "seaweedfs_quantized_keys":   seaweedfs_quantized_keys,
        },
    )

    # ── 5. Write model card ──────────────────────────────────────────────────
    write_model_card(
        merged_model_path,
        meta={
            "version":                    version,
            "base_model":                 base_model,
            "eval_scores":                eval_scores,
            "training_meta":              training_meta,
            "seaweedfs_finetuned_prefix": seaweedfs_finetuned_prefix,
            "seaweedfs_quantized_keys":   seaweedfs_quantized_keys,
        },
    )

    # ── 6. Alert ─────────────────────────────────────────────────────────────
    alerter.send_promotion(
        adapter_id=adapter_id,
        version=version,
        status="promoted",
        base_model=base_model or merged_model_path,
        seaweedfs_path=seaweedfs_finetuned_prefix,
        eval_scores=eval_scores,
    )

    return {
        "new_status":                 "promoted",
        "version":                    version,
        "seaweedfs_finetuned_prefix": seaweedfs_finetuned_prefix,
        "seaweedfs_quantized_keys":   seaweedfs_quantized_keys,
        "actor":                      actor,
    }
