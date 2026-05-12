"""
Post-training quantization pipeline.

Full flow (triggered automatically by job_runner after a successful fine-tune):

  1. Download LoRA adapter weights from Azure Blob (the prefix uploaded just before)
  2. Load base model on CPU and merge LoRA adapter via PEFT merge_and_unload()
  3. Convert merged HF model to GGUF F16 (requires llama.cpp convert script)
  4. Quantize F16 GGUF to each requested level (requires llama-quantize binary)
  5. Upload GGUF artifacts to Azure Blob under gguf/{domain}/{version}/
  6. Upsert rows in the adapter_registry Supabase table

Environment variables:
  FT_QUANT_LEVELS           — comma-separated quant levels, default "q4_k_m,q5_k_m"
  LLAMA_CPP_CONVERT_SCRIPT  — path to convert_hf_to_gguf.py (auto-detected if on PATH)
  LLAMA_CPP_QUANTIZE_BIN    — path to llama-quantize binary (auto-detected if on PATH)
  FT_REGISTRY_CANARY_PCT    — initial canary percentage for new registry rows (default 0)
  FT_QUANT_SKIP             — set to "1" to disable the entire pipeline
"""
from __future__ import annotations

import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

import structlog

log = structlog.get_logger("quantize_pipeline")

_DEFAULT_QUANT_LEVELS = ["q4_k_m", "q5_k_m"]


class QuantizeResult(NamedTuple):
    success: bool
    artifacts: list[dict]
    error: str | None


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def _merge_lora(
    base_model: str,
    adapter_dir: Path,
    merged_dir: Path,
    *,
    local_files_only: bool = False,
) -> None:
    """Load base model + LoRA adapter on CPU, merge, and save as HF safetensors."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log.info("quantize.merge_start", base_model=base_model, adapter=str(adapter_dir))
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
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = model.merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))

    del merged, model, base
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    log.info("quantize.merge_done", merged_dir=str(merged_dir))


# ---------------------------------------------------------------------------
# GGUF conversion helpers
# ---------------------------------------------------------------------------

def _find_convert_script() -> str | None:
    explicit = os.getenv("LLAMA_CPP_CONVERT_SCRIPT", "").strip()
    if explicit and Path(explicit).exists():
        return explicit
    for name in ("convert_hf_to_gguf.py", "convert-hf-to-gguf.py", "convert.py"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _find_quantize_bin() -> str | None:
    explicit = os.getenv("LLAMA_CPP_QUANTIZE_BIN", "").strip()
    if explicit and (Path(explicit).exists() or shutil.which(explicit)):
        return explicit
    for name in ("llama-quantize", "quantize", "llama_quantize"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _gguf_convert(merged_dir: Path, gguf_f16_path: Path, *, log_fn=None) -> bool:
    """Convert HF model directory to GGUF F16. Returns True on success."""
    script = _find_convert_script()
    if not script:
        _log_fn(log_fn, "[quantize] llama.cpp convert script not found — skipping GGUF conversion\n")
        return False

    gguf_f16_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, script,
        str(merged_dir),
        "--outtype", "f16",
        "--outfile", str(gguf_f16_path),
    ]
    _log_fn(log_fn, f"[quantize] convert cmd: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        _log_fn(log_fn, f"[quantize] GGUF convert failed:\n{result.stderr[-2000:]}\n")
        log.error("quantize.convert_failed", stderr=result.stderr[-500:])
        return False

    _log_fn(log_fn, f"[quantize] GGUF F16 created: {gguf_f16_path}\n")
    return True


def _gguf_quantize(
    f16_path: Path,
    output_dir: Path,
    quant_levels: list[str],
    *,
    log_fn=None,
) -> list[Path]:
    """
    Quantize a GGUF F16 file to each requested level using llama-quantize.
    Falls back to returning the F16 path if quantize binary is not available.
    """
    quantize_bin = _find_quantize_bin()
    if not quantize_bin:
        _log_fn(log_fn, "[quantize] llama-quantize not found — using F16 GGUF only\n")
        return [f16_path]

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f16_path.stem  # e.g. "model-F16"
    base_stem = stem.replace("-F16", "").replace("-f16", "") or "model"
    produced: list[Path] = []

    for level in quant_levels:
        out_path = output_dir / f"{base_stem}-{level.upper()}.gguf"
        cmd = [quantize_bin, str(f16_path), str(out_path), level.upper()]
        _log_fn(log_fn, f"[quantize] quantize {level}: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode == 0 and out_path.exists():
            produced.append(out_path)
            _log_fn(log_fn, f"[quantize] {level} done → {out_path}\n")
        else:
            _log_fn(log_fn, f"[quantize] {level} failed:\n{result.stderr[-1000:]}\n")
            log.error("quantize.level_failed", level=level, stderr=result.stderr[-300:])

    return produced if produced else [f16_path]


# ---------------------------------------------------------------------------
# Supabase adapter_registry registration
# ---------------------------------------------------------------------------

def _register_in_adapter_registry(artifacts: list[dict], *, log_fn=None) -> None:
    """Upsert artifact rows into the Supabase adapter_registry table."""
    from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
    import httpx

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        _log_fn(log_fn, "[quantize] Supabase not configured — skipping adapter_registry\n")
        return

    canary_pct = int(os.getenv("FT_REGISTRY_CANARY_PCT", "0"))
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }
    url = (
        f"{SUPABASE_URL}/rest/v1/adapter_registry"
        "?on_conflict=domain,adapter_version,quant_level"
    )

    with httpx.Client(timeout=30) as client:
        for a in artifacts:
            payload = {
                "domain": a["domain"],
                "adapter_version": a["adapter_version"],
                "quant_level": a["quant_level"],
                "blob_key": a["blob_key"],
                "sha256": a["sha256"],
                "size_bytes": a["size_bytes"],
                "is_available": True,
                "blocked": False,
                "canary_pct": canary_pct,
                "rollback_safe": True,
            }
            resp = client.post(url, headers=headers, content=json.dumps(payload))
            if resp.status_code >= 400:
                _log_fn(
                    log_fn,
                    f"[quantize] registry insert failed ({resp.status_code}): {resp.text[:300]}\n",
                )
                log.error(
                    "quantize.registry_failed",
                    status=resp.status_code,
                    domain=a["domain"],
                    version=a["adapter_version"],
                )
            else:
                _log_fn(
                    log_fn,
                    f"[quantize] registered {a['domain']}@{a['adapter_version']} "
                    f"quant={a['quant_level']} in adapter_registry\n",
                )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def quantize_from_local_merged(
    merged_dir: Path,
    domain: str,
    version_name: str,
    *,
    quant_levels: list[str] | None = None,
    log_fn=None,
) -> QuantizeResult:
    """
    Quantize an already-merged HF model that exists on local disk.

    Use this from the Federated Learning aggregator (which already merged
    the LoRA adapter) to avoid a redundant download + re-merge cycle.

    Steps:
      1. Convert merged_dir -> GGUF F16 (if llama.cpp convert script found)
      2. Quantize F16 to each requested level (if llama-quantize found)
      3. Upload GGUF files to Azure Blob: gguf/{domain}/{version_name}/
      4. Upsert rows in adapter_registry (Supabase)

    Falls back to uploading merged HF weights when llama.cpp tools are absent.
    """
    if os.getenv("FT_QUANT_SKIP", "").strip().lower() in {"1", "true", "yes"}:
        _log_fn(log_fn, "[quantize] FT_QUANT_SKIP=1 — pipeline skipped\n")
        return QuantizeResult(success=True, artifacts=[], error=None)

    from fine_tuning.azure_blob_uploader import upload_adapter_weights, upload_gguf_artifacts

    if quant_levels is None:
        env_lvl = os.getenv("FT_QUANT_LEVELS", "").strip()
        quant_levels = (
            [lv.strip().lower() for lv in env_lvl.split(",") if lv.strip()]
            if env_lvl
            else list(_DEFAULT_QUANT_LEVELS)
        )

    _log_fn(
        log_fn,
        f"[quantize] quantize_from_local_merged domain={domain} "
        f"version={version_name} quant_levels={quant_levels}\n",
    )

    import tempfile
    with tempfile.TemporaryDirectory(prefix="ft_quant_fl_") as tmpdir:
        tmp = Path(tmpdir)
        gguf_dir = tmp / "gguf"
        gguf_dir.mkdir()

        try:
            # Step 1 — GGUF conversion
            gguf_f16 = gguf_dir / "model-F16.gguf"
            converted = _gguf_convert(merged_dir, gguf_f16, log_fn=log_fn)

            if converted:
                # Step 2 — quantize to requested levels
                _log_fn(log_fn, f"[quantize] quantizing to levels: {quant_levels}\n")
                _gguf_quantize(gguf_f16, gguf_dir, quant_levels, log_fn=log_fn)

                # Step 3 — upload GGUF artifacts to Azure Blob
                _log_fn(log_fn, "[quantize] uploading GGUF artifacts to Azure Blob\n")
                artifacts = upload_gguf_artifacts(gguf_dir, domain, version_name, log_fn=log_fn)
                if not artifacts:
                    raise RuntimeError("No GGUF files produced to upload")
            else:
                # No llama.cpp — upload merged HF weights instead
                _log_fn(
                    log_fn,
                    "[quantize] llama.cpp tools not found — uploading merged HF weights to Azure Blob\n",
                )
                result = upload_adapter_weights(
                    merged_dir,
                    domain,
                    f"{version_name}_merged",
                    log_fn=log_fn,
                )
                _log_fn(
                    log_fn,
                    f"[quantize] merged HF weights uploaded: {result.prefix} "
                    f"({result.total_bytes:,} bytes, {len(result.files)} files)\n",
                )
                return QuantizeResult(success=True, artifacts=[], error=None)

            # Step 4 — register in adapter_registry
            _log_fn(log_fn, f"[quantize] registering {len(artifacts)} artifact(s) in adapter_registry\n")
            _register_in_adapter_registry(artifacts, log_fn=log_fn)

            _log_fn(
                log_fn,
                f"[quantize] complete — {len(artifacts)} GGUF artifact(s) registered "
                f"(domain={domain}, version={version_name})\n",
            )
            log.info(
                "quantize.fl_complete",
                domain=domain,
                version=version_name,
                num_artifacts=len(artifacts),
            )
            return QuantizeResult(success=True, artifacts=artifacts, error=None)

        except Exception as exc:
            _log_fn(log_fn, f"[quantize] ERROR in quantize_from_local_merged: {exc}\n")
            log.exception("quantize.fl_failed", domain=domain, version=version_name)
            return QuantizeResult(success=False, artifacts=[], error=str(exc))


def run_quantization_pipeline(
    base_model: str,
    adapter_prefix: str,
    domain: str,
    version_name: str,
    *,
    quant_levels: list[str] | None = None,
    local_files_only: bool = False,
    log_fn=None,
) -> QuantizeResult:
    """
    Full post-training quantization pipeline.

    Downloads LoRA weights from Azure Blob, merges them into the base model,
    converts to GGUF, quantizes to each requested level, uploads GGUF files
    back to Azure Blob, and registers them in the adapter_registry table.

    Args:
        base_model: HuggingFace repo ID or local path for the base model.
        adapter_prefix: Azure Blob prefix where LoRA adapter was uploaded
            (e.g. "adapters/acord/v3").
        domain: Registry domain label (e.g. "acord", "broker").
        version_name: Version label used in S3 keys and registry
            (e.g. "v3").
        quant_levels: GGUF quant levels to produce. Reads FT_QUANT_LEVELS
            env var if None; defaults to ["q4_k_m", "q5_k_m"].
        local_files_only: Pass True if base_model is a local path only.
        log_fn: Optional callable(str) for writing log lines to a file.
    """
    if os.getenv("FT_QUANT_SKIP", "").strip().lower() in {"1", "true", "yes"}:
        _log_fn(log_fn, "[quantize] FT_QUANT_SKIP=1 — pipeline skipped\n")
        return QuantizeResult(success=True, artifacts=[], error=None)

    from fine_tuning.azure_blob_uploader import (
        download_adapter,
        upload_adapter_weights,
        upload_gguf_artifacts,
    )

    if quant_levels is None:
        env_lvl = os.getenv("FT_QUANT_LEVELS", "").strip()
        quant_levels = (
            [l.strip().lower() for l in env_lvl.split(",") if l.strip()]
            if env_lvl
            else list(_DEFAULT_QUANT_LEVELS)
        )

    _log_fn(
        log_fn,
        f"[quantize] starting pipeline domain={domain} version={version_name} "
        f"quant_levels={quant_levels}\n",
    )

    with tempfile.TemporaryDirectory(prefix="ft_quant_") as tmpdir:
        tmp = Path(tmpdir)
        adapter_local = tmp / "adapter"
        merged_local = tmp / "merged"
        gguf_dir = tmp / "gguf"
        gguf_dir.mkdir()

        try:
            # Step 1 — download adapter from Azure Blob
            _log_fn(log_fn, f"[quantize] downloading adapter: {adapter_prefix}\n")
            downloaded = download_adapter(
                adapter_prefix, adapter_local, log_fn=log_fn
            )
            if not downloaded:
                raise RuntimeError(
                    f"No files found at Azure Blob prefix: {adapter_prefix}"
                )

            # Step 2 — merge LoRA into base model
            _log_fn(log_fn, f"[quantize] merging LoRA into {base_model} ...\n")
            _merge_lora(
                base_model,
                adapter_local,
                merged_local,
                local_files_only=local_files_only,
            )

            # Step 3 — GGUF conversion
            gguf_f16 = gguf_dir / "model-F16.gguf"
            converted = _gguf_convert(merged_local, gguf_f16, log_fn=log_fn)

            if converted:
                # Step 4 — quantize to requested levels
                _log_fn(log_fn, f"[quantize] quantizing to levels: {quant_levels}\n")
                _gguf_quantize(gguf_f16, gguf_dir, quant_levels, log_fn=log_fn)
            else:
                # No GGUF tools — upload the merged HF model as a fallback
                _log_fn(
                    log_fn,
                    "[quantize] llama.cpp tools unavailable — uploading merged HF weights\n",
                )
                upload_adapter_weights(
                    merged_local,
                    domain,
                    f"{version_name}_merged",
                    log_fn=log_fn,
                )
                _log_fn(log_fn, "[quantize] merged HF weights uploaded (no GGUF produced)\n")
                return QuantizeResult(success=True, artifacts=[], error=None)

            # Step 5 — upload GGUF artifacts
            _log_fn(log_fn, "[quantize] uploading GGUF artifacts to Azure Blob\n")
            artifacts = upload_gguf_artifacts(gguf_dir, domain, version_name, log_fn=log_fn)
            if not artifacts:
                raise RuntimeError("No GGUF files were produced to upload")

            # Step 6 — register in adapter_registry
            _log_fn(
                log_fn,
                f"[quantize] registering {len(artifacts)} artifact(s) in adapter_registry\n",
            )
            _register_in_adapter_registry(artifacts, log_fn=log_fn)

            _log_fn(log_fn, f"[quantize] pipeline complete — {len(artifacts)} artifact(s) registered\n")
            log.info(
                "quantize.pipeline_complete",
                domain=domain,
                version=version_name,
                num_artifacts=len(artifacts),
            )
            return QuantizeResult(success=True, artifacts=artifacts, error=None)

        except Exception as exc:
            _log_fn(log_fn, f"[quantize] pipeline ERROR: {exc}\n")
            log.exception("quantize.pipeline_failed", domain=domain, version=version_name)
            return QuantizeResult(success=False, artifacts=[], error=str(exc))


def _log_fn(fn, msg: str) -> None:
    """Write msg to log_fn if provided, and always emit to structlog."""
    if fn:
        try:
            fn(msg)
        except Exception:
            pass
    log.debug("quantize.log", msg=msg.strip())
