"""
Federated Learning aggregation pipeline — FedAvg over LoRA adapters.

Full flow (triggered after a federated_round reaches 'aggregating' status):

  1.  Fetch all federated_updates for the round from Supabase
  2.  Download each device's LoRA adapter from Azure Blob
        gradients/{model_id}/round-{N}/{device_id}/
  3.  FedAvg: element-wise average of every LoRA weight tensor
  4.  Save averaged adapter to local temp dir
  5.  Upload averaged adapter -> Azure Blob: adapters/federated/v{N}/
  6.  Merge adapter into base model (local FINE_TUNE_BASE_MODEL path)
  7.  Upload merged full model -> Azure Blob: finetuned/v{N}/
  8.  Update version pointer: Azure Blob finetuned/latest.txt = N
  9.  Quantize the local merged model (no re-download, no re-merge)
        -> GGUF Q4_K_M + Q5_K_M (if llama.cpp tools present)
        -> Azure Blob: gguf/federated/v{N}/
        -> Supabase adapter_registry (Electron picks this up)
  10. Mark federated_round as completed in Supabase

Azure Blob key layout after completion (container = fideon-models):
  adapters/federated/v{N}/adapter_model.safetensors   <- averaged LoRA weights
  adapters/federated/v{N}/adapter_config.json
  finetuned/v{N}/model-*.safetensors                  <- full merged HF model
  finetuned/v{N}/config.json
  finetuned/v{N}/tokenizer.json  ...
  finetuned/latest.txt                                <- N  (version pointer)
  gguf/federated/v{N}/model-Q4_K_M.gguf              <- ready for Electron
  gguf/federated/v{N}/model-Q5_K_M.gguf

Environment variables:
  FINE_TUNE_BASE_MODEL         local HF model path or HF repo id
  FINE_TUNE_LOCAL_FILES_ONLY   "true" if base model is local-only
  AZURE_BLOB_ACCOUNT_URL       Azure Blob Storage account URL
  AZURE_BLOB_SAS_TOKEN         SAS token (without leading '?')
  AZURE_BLOB_CONTAINER         container name (default: fideon-models)
  FT_QUANT_LEVELS              comma-separated levels (default q4_k_m,q5_k_m)
  FT_QUANT_SKIP                "1" to skip quantization step
"""
from __future__ import annotations

import gc
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

import httpx
import structlog

log = structlog.get_logger("federated_aggregator")

_LATEST_POINTER_KEY = "finetuned/latest.txt"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class AggregationResult(NamedTuple):
    success: bool
    new_version: str              # e.g. "v9"
    adapter_prefix: str           # adapters/federated/v9
    finetuned_prefix: str         # finetuned/v9
    gguf_prefix: str              # gguf/federated/v9  (empty if skipped)
    quant_artifacts: list[dict]   # adapter_registry rows
    error: str | None


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _sb_headers() -> dict[str, str]:
    from app.core.config import SUPABASE_SERVICE_ROLE_KEY
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_round_updates(round_id: str, model_id: str, round_number: int) -> list[dict]:
    """Return all federated_updates for this round."""
    from app.core.config import SUPABASE_URL
    q = "&".join([
        "select=id,device_id,storage_path,gradient_size_bytes,metrics",
        f"model_id=eq.{quote(model_id, safe='')}",
        f"round_number=eq.{round_number}",
    ])
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/federated_updates?{q}",
            headers=_sb_headers(),
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"fetch_updates failed ({resp.status_code}): {resp.text}")
    return resp.json() or []


def _patch_round(round_id: str, payload: dict) -> None:
    from app.core.config import SUPABASE_URL
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{SUPABASE_URL}/rest/v1/federated_rounds?id=eq.{quote(round_id, safe='')}",
            headers=_sb_headers(),
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"patch_round failed ({resp.status_code}): {resp.text}")


def _record_aggregation(
    round_id: str,
    new_version: str,
    adapter_prefix: str,
    finetuned_prefix: str,
    gguf_prefix: str,
    num_contributions: int,
) -> None:
    """Insert into federated_aggregations table (best-effort; table may not exist yet)."""
    from app.core.config import SUPABASE_URL
    payload = {
        "round_id": round_id,
        "version": new_version,
        "adapter_prefix": adapter_prefix,
        "finetuned_prefix": finetuned_prefix,
        "gguf_prefix": gguf_prefix,
        "num_contributions": num_contributions,
        "aggregated_at": datetime.now(timezone.utc).isoformat(),
    }
    headers = dict(_sb_headers())
    headers["Prefer"] = "return=minimal"
    try:
        with httpx.Client(timeout=15) as client:
            client.post(
                f"{SUPABASE_URL}/rest/v1/federated_aggregations",
                headers=headers,
                content=json.dumps(payload),
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Azure Blob helpers
# ---------------------------------------------------------------------------

def _read_latest_version() -> int:
    """Read finetuned/latest.txt from Azure Blob. Returns int version number (0 if absent)."""
    from fine_tuning.azure_blob_uploader import get_latest_version
    return get_latest_version()


def _write_latest_version(version_int: int) -> None:
    from fine_tuning.azure_blob_uploader import write_latest_version
    write_latest_version(version_int)


def _upload_directory(local_dir: Path, prefix: str, *, log_fn=None) -> list[dict]:
    """Upload every file in local_dir to Azure Blob under prefix/."""
    from fine_tuning.azure_blob_uploader import upload_directory
    return upload_directory(local_dir, prefix, log_fn=log_fn)


def _download_device_adapter(storage_path: str, dest_dir: Path, *, log_fn=None) -> bool:
    """Download all blobs under storage_path prefix from Azure Blob into dest_dir."""
    from fine_tuning.azure_blob_uploader import download_adapter
    prefix = storage_path.rstrip("/")
    downloaded = download_adapter(prefix, dest_dir, log_fn=log_fn)
    return len(downloaded) > 0


# ---------------------------------------------------------------------------
# FedAvg core
# ---------------------------------------------------------------------------

def _load_adapter_weights(adapter_dir: Path) -> dict:
    """
    Load LoRA adapter weight tensors from a directory.
    Tries safetensors first, then torch .bin/.pt files.
    """
    import torch

    sf_files = sorted(adapter_dir.glob("*.safetensors"))
    if sf_files:
        try:
            from safetensors.torch import load_file
            merged: dict = {}
            for f in sf_files:
                merged.update(load_file(str(f)))
            return merged
        except ImportError:
            pass  # safetensors not installed; fall through

    bin_files = sorted(adapter_dir.glob("*.bin")) + sorted(adapter_dir.glob("*.pt"))
    if bin_files:
        merged = {}
        for f in bin_files:
            state = torch.load(str(f), map_location="cpu", weights_only=True)
            if isinstance(state, dict):
                merged.update(state)
        return merged

    raise RuntimeError(f"No adapter weight files (.safetensors / .bin / .pt) found in {adapter_dir}")


def _fedavg(state_dicts: list[dict]) -> dict:
    """
    Federated Averaging: element-wise mean across all adapter tensors.
    All submissions must share the same LoRA architecture (identical key set).
    """
    import torch

    if not state_dicts:
        raise ValueError("FedAvg called with empty state_dicts list")
    if len(state_dicts) == 1:
        return state_dicts[0]

    avg: dict = {}
    for key in state_dicts[0]:
        tensors = [sd[key].float() for sd in state_dicts if key in sd]
        if tensors:
            avg[key] = torch.stack(tensors).mean(dim=0)
    return avg


def _save_averaged_adapter(
    avg_weights: dict,
    src_dir: Path,
    dest_dir: Path,
) -> None:
    """
    Persist averaged weights as adapter_model.safetensors and copy
    non-weight config files (adapter_config.json, tokenizer files, etc.)
    from the first device's adapter directory.
    """
    import shutil
    from safetensors.torch import save_file

    dest_dir.mkdir(parents=True, exist_ok=True)
    save_file(avg_weights, str(dest_dir / "adapter_model.safetensors"))

    for fname in [
        "adapter_config.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "special_tokens_map.json",
        "generation_config.json",
    ]:
        src = src_dir / fname
        if src.exists():
            shutil.copy2(str(src), str(dest_dir / fname))


# ---------------------------------------------------------------------------
# Merge LoRA adapter into base model
# ---------------------------------------------------------------------------

def _merge_adapter_to_base(
    base_model: str,
    adapter_dir: Path,
    merged_dir: Path,
    *,
    local_files_only: bool = False,
    log_fn=None,
) -> None:
    """
    Load base model on CPU, attach averaged LoRA adapter, merge_and_unload(),
    and save as full HF safetensors model.

    The merged model in merged_dir is then uploaded to Azure Blob AND passed
    directly to quantization — no re-download, no re-merge.
    """
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if log_fn:
        log_fn(f"[fedavg] loading base model: {base_model}\n")

    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    if log_fn:
        log_fn("[fedavg] merging averaged LoRA adapter into base model...\n")

    peft_model = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = peft_model.merge_and_unload()

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))

    del merged, peft_model, base
    gc.collect()
    try:
        import torch as _t
        if _t.cuda.is_available():
            _t.cuda.empty_cache()
    except Exception:
        pass

    if log_fn:
        files = [f.name for f in merged_dir.iterdir() if f.is_file()]
        log_fn(f"[fedavg] merged model saved ({len(files)} files): {files}\n")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_aggregation(
    round_id: str,
    model_id: str,
    round_number: int,
    *,
    log_fn=None,
) -> AggregationResult:
    """
    Execute the full FedAvg -> Azure Blob storage -> quantization pipeline.

    Designed to run in a background thread (called via asyncio.to_thread).
    All exceptions are caught; round status is updated to 'failed' on error.

    Returns AggregationResult with paths for every artifact stored in Azure Blob.
    """
    from fine_tuning.quantize_pipeline import quantize_from_local_merged

    def _log(msg: str) -> None:
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass
        log.info("fedavg", msg=msg.strip())

    base_model = os.getenv("FINE_TUNE_BASE_MODEL", "").strip()
    local_files_only = (
        os.getenv("FINE_TUNE_LOCAL_FILES_ONLY", "").strip().lower()
        in {"1", "true", "yes"}
    )

    if not base_model:
        err = "FINE_TUNE_BASE_MODEL is not set — cannot merge LoRA into base"
        _log(f"[fedavg] ERROR: {err}\n")
        try:
            _patch_round(round_id, {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": err,
            })
        except Exception:
            pass
        return AggregationResult(
            success=False, new_version="", adapter_prefix="",
            finetuned_prefix="", gguf_prefix="", quant_artifacts=[], error=err,
        )

    with tempfile.TemporaryDirectory(prefix="fl_agg_") as tmpdir:
        tmp = Path(tmpdir)

        try:
            # ----------------------------------------------------------------
            # Step 1 — fetch all gradient submissions for this round
            # ----------------------------------------------------------------
            _log(f"[fedavg] round_id={round_id} model={model_id} round={round_number}\n")
            _log("[fedavg] fetching device submissions from Supabase...\n")
            updates = _fetch_round_updates(round_id, model_id, round_number)
            if not updates:
                raise RuntimeError(
                    f"No federated_updates found for round_id={round_id}"
                )
            _log(f"[fedavg] {len(updates)} device submission(s) found\n")

            # ----------------------------------------------------------------
            # Step 2 — download each device's LoRA adapter from Azure Blob
            # ----------------------------------------------------------------
            state_dicts: list[dict] = []
            first_adapter_dir: Path | None = None

            for i, upd in enumerate(updates):
                storage_path = (upd.get("storage_path") or "").strip()
                if not storage_path:
                    _log(f"[fedavg] skip update {upd.get('id')} — no storage_path\n")
                    continue

                device_dir = tmp / f"device_{i}"
                device_dir.mkdir()
                _log(f"[fedavg] downloading device {upd.get('device_id')} from {storage_path}\n")

                ok = _download_device_adapter(storage_path, device_dir, log_fn=log_fn)
                if not ok:
                    _log(f"[fedavg] WARNING: nothing at {storage_path} — skipping\n")
                    continue

                try:
                    sd = _load_adapter_weights(device_dir)
                    state_dicts.append(sd)
                    if first_adapter_dir is None:
                        first_adapter_dir = device_dir
                    _log(
                        f"[fedavg] loaded {len(sd)} tensors "
                        f"from device {upd.get('device_id')}\n"
                    )
                except Exception as exc:
                    _log(
                        f"[fedavg] WARNING: cannot load weights for "
                        f"device {upd.get('device_id')}: {exc}\n"
                    )

            if not state_dicts:
                raise RuntimeError(
                    "No valid adapter weights could be loaded from any device submission"
                )

            # ----------------------------------------------------------------
            # Step 3 — FedAvg: average all adapter tensors
            # ----------------------------------------------------------------
            _log(
                f"[fedavg] running FedAvg over {len(state_dicts)} "
                f"adapter(s)...\n"
            )
            averaged = _fedavg(state_dicts)
            _log(f"[fedavg] averaged {len(averaged)} parameter tensors\n")

            # ----------------------------------------------------------------
            # Step 4 — save averaged adapter to temp dir
            # ----------------------------------------------------------------
            avg_adapter_dir = tmp / "averaged_adapter"
            _save_averaged_adapter(averaged, first_adapter_dir, avg_adapter_dir)
            del averaged, state_dicts
            gc.collect()

            # ----------------------------------------------------------------
            # Step 5 — determine new version number from Azure Blob pointer
            # ----------------------------------------------------------------
            current_v = _read_latest_version()
            new_v = current_v + 1
            new_version = f"v{new_v}"
            _log(
                f"[fedavg] Azure Blob current version=v{current_v}, "
                f"new version={new_version}\n"
            )

            # ----------------------------------------------------------------
            # Step 6 — upload averaged LoRA adapter to Azure Blob
            # ----------------------------------------------------------------
            adapter_prefix = f"adapters/federated/{new_version}"
            _log(f"[fedavg] uploading averaged adapter -> {adapter_prefix}/\n")
            _upload_directory(avg_adapter_dir, adapter_prefix, log_fn=log_fn)

            # ----------------------------------------------------------------
            # Step 7 — merge averaged adapter into base model (CPU)
            # ----------------------------------------------------------------
            merged_dir = tmp / "merged_model"
            _merge_adapter_to_base(
                base_model,
                avg_adapter_dir,
                merged_dir,
                local_files_only=local_files_only,
                log_fn=log_fn,
            )

            # ----------------------------------------------------------------
            # Step 8 — upload merged full model to Azure Blob
            # ----------------------------------------------------------------
            finetuned_prefix = f"finetuned/{new_version}"
            _log(f"[fedavg] uploading merged model -> {finetuned_prefix}/\n")
            _upload_directory(merged_dir, finetuned_prefix, log_fn=log_fn)

            # Update the version pointer so the next FL round increments correctly
            _write_latest_version(new_v)
            _log(f"[fedavg] finetuned/latest.txt updated -> {new_v}\n")

            # ----------------------------------------------------------------
            # Step 9 — quantize using the LOCAL merged_dir (no re-download,
            #          no re-merge — the model is already on disk in this tmpdir)
            # ----------------------------------------------------------------
            _log("[fedavg] quantizing merged model...\n")
            gguf_prefix = f"gguf/federated/{new_version}"
            quant_result = quantize_from_local_merged(
                merged_dir,
                "federated",
                new_version,
                log_fn=log_fn,
            )
            if quant_result.success:
                _log(
                    f"[fedavg] quantization complete: "
                    f"{len(quant_result.artifacts)} artifact(s) registered\n"
                )
            else:
                _log(
                    f"[fedavg] WARNING: quantization failed "
                    f"(weights still stored in HF format): {quant_result.error}\n"
                )
                gguf_prefix = ""

            # ----------------------------------------------------------------
            # Step 10 — mark round completed in Supabase
            # ----------------------------------------------------------------
            _patch_round(round_id, {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "aggregated_version": new_version,
            })
            _log(f"[fedavg] round marked completed — aggregated_version={new_version}\n")

            # Best-effort: record full provenance
            _record_aggregation(
                round_id,
                new_version,
                adapter_prefix,
                finetuned_prefix,
                gguf_prefix,
                len(updates),
            )

            _log(
                f"[fedavg] *** aggregation pipeline finished ***\n"
                f"[fedavg]   averaged adapter  : azure://{adapter_prefix}/\n"
                f"[fedavg]   merged HF model   : azure://{finetuned_prefix}/\n"
                f"[fedavg]   GGUF artifacts    : azure://{gguf_prefix}/\n"
                f"[fedavg]   adapter_registry  : domain=federated version={new_version}\n"
            )

            return AggregationResult(
                success=True,
                new_version=new_version,
                adapter_prefix=adapter_prefix,
                finetuned_prefix=finetuned_prefix,
                gguf_prefix=gguf_prefix,
                quant_artifacts=quant_result.artifacts,
                error=None,
            )

        except Exception as exc:
            err_msg = str(exc)
            _log(f"[fedavg] PIPELINE FAILED: {err_msg}\n")
            log.exception("fedavg.pipeline_failed", round_id=round_id)
            try:
                _patch_round(round_id, {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": err_msg[:2000],
                })
            except Exception:
                pass
            return AggregationResult(
                success=False,
                new_version="",
                adapter_prefix="",
                finetuned_prefix="",
                gguf_prefix="",
                quant_artifacts=[],
                error=err_msg,
            )
