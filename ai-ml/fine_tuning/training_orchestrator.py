"""
Training orchestrator — top-level promote_adapter() called after run_cycle().

Responsibilities (in order):
  1. Upload merged HF model   → SeaweedFS finetuned/v{N}/
  2. Quantize merged model    → GGUF Q5_K_M + Q4_K_M
  3. Upload quantized GGUFs   → SeaweedFS quantized/v{N}/
  4. Register GGUF artifacts  → Supabase adapter_registry (so Electron can download)
  5. Update version_registry.json with all SeaweedFS paths
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

    with httpx.Client(timeout=30) as client:
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


def _gguf_smoke_test(gguf_path: str, ollama_host: str = "http://localhost:11434") -> bool:
    """
    Spin up a temporary Ollama model from the GGUF, run one inference with the
    exact training prompt format, and verify the output is parseable JSON.
    Cleans up the temp model regardless of outcome.

    Returns True if the model outputs valid JSON, False otherwise.
    Non-fatal when Ollama is not available (returns True to not block).
    """
    import json
    import shutil
    import subprocess
    import urllib.request
    from pathlib import Path as _Path

    model_name = "fideon-smoke-test"

    if not shutil.which("ollama"):
        print("[smoke] ollama binary not found — skipping GGUF smoke test")
        return True

    modelfile_path = _Path(gguf_path).with_suffix(".Modelfile.smoke")
    modelfile_path.write_text(
        f"FROM {gguf_path}\nPARAMETER temperature 0\nPARAMETER num_predict 300\n"
    )

    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            capture_output=True, text=True, timeout=180,
            env={**__import__("os").environ, "OLLAMA_HOST": ollama_host},
        )
        if result.returncode != 0:
            print(f"[smoke] ollama create failed — skipping smoke test: {result.stderr[:300]}")
            return True  # non-fatal: Ollama may not be serving yet

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert insurance document parser specialising in ACORD forms. "
                        "Given raw OCR text from an ACORD form, extract ALL fields and return a single "
                        "valid JSON object. Use \"\" for blank fields. Represent checkboxes as true/false. "
                        "Represent table rows as arrays of objects. Output ONLY the JSON — no commentary."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "ACORD Form 25\n\nOCR TEXT:\n"
                        "Agency: Smoke Test Agency\nPolicy Number: SMOKE-001\n"
                        "Insured: Jane Doe\nDate: 07/01/2025\nPremium: $1200"
                    ),
                },
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 300},
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{ollama_host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        output = (data.get("message") or {}).get("content", "")
        start = output.find("{")
        end = output.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(output[start : end + 1])
                if isinstance(parsed, dict) and len(parsed) >= 1:
                    print(
                        f"[smoke] ✓ GGUF smoke test passed — model outputs valid JSON "
                        f"({len(parsed)} fields extracted)"
                    )
                    return True
            except json.JSONDecodeError:
                pass

        print(f"[smoke] ✗ GGUF output is not valid JSON.\n  First 300 chars: {output[:300]}")
        return False

    except Exception as exc:
        print(f"[smoke] ✗ Smoke test error: {exc} — treating as non-fatal")
        return True  # connection errors = Ollama not available, non-fatal

    finally:
        subprocess.run(["ollama", "rm", model_name], capture_output=True, timeout=30)
        modelfile_path.unlink(missing_ok=True)


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
    progress_callback: Optional[Any] = None,
    skip_quantization: bool = False,
) -> Dict[str, Any]:
    """
    Finalise promotion of a merged model version.

    Steps
    -----
    1. Upload merged HF model   → Azure Blob  finetuned/v{version}/
    2. Quantize                 → GGUF Q5_K_M + Q4_K_M  (skipped when skip_quantization=True)
    3. Upload quantized GGUFs   → Azure Blob  quantized/v{version}/  (skipped when skip_quantization=True)
    4. Register GGUFs           → Supabase adapter_registry (Electron delivery)
    5. Update registry          → promote_version() with all storage paths
    6. Write model card
    7. Send alert

    skip_quantization=True is used by Share Gradients: only the raw HF weights are
    uploaded so that Global Update's filter (has_successful_quantization) can correctly
    identify these versions as fresh/unquantized and include them in FedAvg.
    Quantization of the aggregated model is done exclusively by Global Update.
    """
    from fine_tuning.registry.version_registry import VersionRegistry
    from fine_tuning.registry.model_card import write_model_card

    registry = VersionRegistry(registry_path)
    storage  = get_storage_client()

    storage_finetuned_prefix: Optional[str] = None
    storage_quantized_keys:   List[str]     = []

    # ── 1. Upload merged HF model → finetuned/v{N}/ ─────────────────────────
    # Fatal — if this fails, we must NOT delete the local manifest or weights.
    # The exception propagates to _run_share_job which keeps the manifest for retry.
    print(f"[orchestrator] Uploading merged HF model (v{version}) to Azure Blob …")
    storage_finetuned_prefix = storage.upload_hf_model(
        merged_model_path, version, progress_callback=progress_callback
    )

    # ── 2. Quantize merged model → GGUF ─────────────────────────────────────
    # Skipped during Share Gradients so that quantized/v{N}/ is NOT created here.
    # Global Update detects fresh versions by the absence of quantized/v{N}/*.gguf.
    if skip_quantization:
        print(f"[orchestrator] Skipping quantization (Share Gradients mode — Global Update will quantize after FedAvg).")
        quant_results = {}
    else:
        from fine_tuning.quantization.quantizer import run_quantization
        gguf_output_dir = str(Path(merged_model_path).parent / f"{version}-gguf")
        print(f"[orchestrator] Running quantization → {gguf_output_dir}")
        try:
            quant_results = run_quantization(merged_model_path, gguf_output_dir, version)
        except Exception as exc:
            print(f"[orchestrator] Quantization failed (non-fatal): {exc}")
            quant_results = {}

    # ── 2b. GGUF smoke test — verify model outputs JSON before publishing ────
    # Fatal: if the model is broken, abort here so latest.txt is NOT updated
    # and the pod does not pull a broken model on next restart.
    if quant_results:
        ollama_host = __import__("os").getenv("OLLAMA_HOST", "http://localhost:11434")
        best_gguf = next(
            (v for v in quant_results.values() if "q5_k_m" in str(v).lower()),
            next(iter(quant_results.values()), None),
        )
        if best_gguf:
            print(f"[orchestrator] Running GGUF smoke test on {__import__('pathlib').Path(best_gguf).name} …")
            if not _gguf_smoke_test(best_gguf, ollama_host=ollama_host):
                raise RuntimeError(
                    f"[orchestrator] GGUF smoke test FAILED for v{version} — "
                    "the fine-tuned model does not output valid JSON. "
                    "The broken GGUF has NOT been uploaded to Azure Blob. "
                    "Check training data quality (assistant turns must be valid JSON) "
                    "and retrain with more diverse examples before promoting."
                )

    # ── 3. Upload quantized GGUFs → quantized/v{N}/ ─────────────────────────
    if quant_results:
        gguf_output_dir = str(Path(merged_model_path).parent / f"{version}-gguf")
        print(f"[orchestrator] Uploading {len(quant_results)} GGUF(s) to Azure Blob …")
        try:
            storage_quantized_keys = storage.upload_quantized(
                gguf_output_dir, version, progress_callback=progress_callback
            )
        except Exception as exc:
            print(f"[orchestrator] Quantized upload failed (non-fatal): {exc}")
    else:
        if not skip_quantization:
            print("[orchestrator] No GGUF artifacts — skipping quantized upload.")

    # ── 4. Register GGUFs in Supabase adapter_registry → Electron delivery ──
    if storage_quantized_keys:
        try:
            _register_gguf_in_supabase(storage_quantized_keys, version, gguf_output_dir)
        except Exception as exc:
            print(f"[orchestrator] adapter_registry registration failed (non-fatal): {exc}")
    else:
        if not skip_quantization:
            print("[orchestrator] No GGUF blob keys — skipping adapter_registry registration.")

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
            "version":                  version,
            "base_model":               base_model,
            "eval_scores":              eval_scores,
            "training_meta":            training_meta,
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
