"""
Training orchestrator — top-level promote_adapter() called after run_cycle().

Responsibilities (in order):
  1. Upload merged HF model   → Azure Blob  finetuned/v{N}/
  2. Quantize merged model    → GGUF Q5_K_M + Q4_K_M
  3. Upload quantized GGUFs   → Azure Blob  quantized/v{N}/
  4. Register GGUF artifacts  → Supabase adapter_registry (so Electron can download)
  5. Update version_registry.json with all storage paths
  6. Write model card
  7. Send promotion alert

Required env vars for Electron delivery (set on the pod):
  SUPABASE_URL              — e.g. https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY — service role key
  FT_DOMAIN                 — domain tag written to adapter_registry (default: "acord")
  FT_REGISTRY_CANARY_PCT    — % of devices that get the update (default: 100)
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fine_tuning.storage_client import get_storage_client
from fine_tuning.observability.alerting import alerter


def _register_gguf_in_supabase(
    gguf_s3_keys: List[str],
    version: int,
    gguf_dir: str,
) -> None:
    """
    Upsert each uploaded GGUF artifact into Supabase adapter_registry so that
    Electron's GET /api/v1/adapter/latest picks it up for download.

    Schema (from migrations/20260411000000_adapter_registry.sql):
      domain, adapter_version, filename, quant_level, sha256, size_bytes,
      blob_key, min_electron_ver, canary_pct, rollback_safe, is_available, blocked

    Unique constraint: (domain, adapter_version, quant_level)

    Non-fatal — logs a warning and returns if Supabase is not configured.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    domain       = os.getenv("FT_DOMAIN", "acord").strip()
    canary_pct   = int(os.getenv("FT_REGISTRY_CANARY_PCT", "100"))
    # adapter_version: "1.{N}.0" matches SLM v1.N naming, e.g. version=13 → "1.13.0"
    adapter_version = os.getenv("FT_ADAPTER_VERSION", f"1.{version}.0").strip()

    if not supabase_url or not supabase_key:
        print(
            "[orchestrator] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set "
            "— skipping adapter_registry registration. Electron won't see this version."
        )
        return

    try:
        import httpx
    except ImportError:
        print("[orchestrator] httpx not installed — skipping adapter_registry registration.")
        return

    gguf_path = Path(gguf_dir)
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }
    url = (
        f"{supabase_url}/rest/v1/adapter_registry"
        "?on_conflict=domain,adapter_version,quant_level"
    )

    def _sha256(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _parse_quant(fname: str) -> str:
        low = fname.lower()
        for q in ["q5_k_m", "q4_k_m", "q8_0", "q6_k", "q3_k_m", "q2_k", "f16", "f32"]:
            if q in low:
                return q
        return "unknown"

    with httpx.Client(timeout=120) as client:
        for key in gguf_s3_keys:
            filename = key.split("/")[-1]        # e.g. "model-q5_k_m.gguf"
            local_f  = gguf_path / filename
            if not local_f.exists():
                print(f"[orchestrator] GGUF not found locally for registry: {filename}")
                continue
            quant     = _parse_quant(filename)
            sha256hex = _sha256(local_f)
            size      = local_f.stat().st_size
            row = {
                "domain":           domain,
                "adapter_version":  adapter_version,
                "filename":         filename,       # required column from migration
                "quant_level":      quant,
                "sha256":           f"sha256:{sha256hex}",
                "size_bytes":       size,
                "blob_key":         key,            # actual S3 key used to generate presigned URL
                "is_available":     True,
                "blocked":          False,
                "canary_pct":       canary_pct,
                "min_electron_ver": "0.0.0",
                "rollback_safe":    True,
            }
            resp = client.post(url, headers=headers, json=row)
            if resp.is_success:
                print(
                    f"[orchestrator] adapter_registry ✓ {domain}@{adapter_version} "
                    f"quant={quant}  blob={key}"
                )
            else:
                print(
                    f"[orchestrator] adapter_registry FAILED {quant} "
                    f"({resp.status_code}): {resp.text[:300]}"
                )


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
    1. Upload merged HF model   → Azure Blob  finetuned/v{version}/
    2. Quantize                 → GGUF Q5_K_M + Q4_K_M (skipped if llama.cpp absent)
    3. Upload quantized GGUFs   → Azure Blob  quantized/v{version}/
    4. Register GGUFs           → Supabase adapter_registry (Electron delivery)
    5. Update registry          → promote_version() with all storage paths
    6. Write model card
    7. Send alert
    """
    from fine_tuning.registry.version_registry import VersionRegistry
    from fine_tuning.registry.model_card import write_model_card
    from fine_tuning.quantization.quantizer import run_quantization

    registry = VersionRegistry(registry_path)
    storage  = get_storage_client()

    storage_finetuned_prefix: Optional[str] = None
    storage_quantized_keys:   List[str]     = []

    # ── 1. Upload merged HF model → finetuned/v{N}/ ─────────────────────────
    # Fatal: if upload fails, do not register the version with a null prefix.
    print(f"[orchestrator] Uploading merged HF model (v{version}) to storage …")
    storage_finetuned_prefix = storage.upload_hf_model(merged_model_path, version)

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
        print(f"[orchestrator] Uploading {len(quant_results)} GGUF(s) to storage …")
        try:
            storage_quantized_keys = storage.upload_quantized(gguf_output_dir, version)
        except Exception as exc:
            print(f"[orchestrator] Quantized upload failed (non-fatal): {exc}")
    else:
        print("[orchestrator] No GGUF artifacts — skipping quantized upload.")

    # ── 4. Register GGUFs in Supabase adapter_registry → Electron delivery ──
    if storage_quantized_keys:
        try:
            _register_gguf_in_supabase(storage_quantized_keys, version, gguf_output_dir)
        except Exception as exc:
            print(f"[orchestrator] adapter_registry registration failed (non-fatal): {exc}")
    else:
        print("[orchestrator] No GGUF S3 keys — skipping adapter_registry registration.")

    # ── 5. Update local registry ─────────────────────────────────────────────
    registry.promote_version(
        version=version,
        merged_model_path=merged_model_path,
        adapter_path=adapter_path,
        eval_scores=eval_scores,
        training_meta={
            **training_meta,
            "storage_finetuned_prefix": storage_finetuned_prefix,
            "storage_quantized_keys":   storage_quantized_keys,
        },
    )

    # ── 6. Write model card ──────────────────────────────────────────────────
    write_model_card(
        merged_model_path,
        meta={
            "version":                    version,
            "base_model":                 base_model,
            "eval_scores":                eval_scores,
            "training_meta":              training_meta,
            "storage_finetuned_prefix": storage_finetuned_prefix,
            "storage_quantized_keys":   storage_quantized_keys,
        },
    )

    # ── 7. Alert ─────────────────────────────────────────────────────────────
    alerter.send_promotion(
        adapter_id=adapter_id,
        version=version,
        status="promoted",
        base_model=base_model or merged_model_path,
        seaweedfs_path=storage_finetuned_prefix,
        eval_scores=eval_scores,
    )

    return {
        "new_status":               "promoted",
        "version":                  version,
        "storage_finetuned_prefix": storage_finetuned_prefix,
        "storage_quantized_keys":   storage_quantized_keys,
        "actor":                    actor,
    }
