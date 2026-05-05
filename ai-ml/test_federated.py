"""
Federated Learning Diagnostic & Test Runner
============================================
Run this directly on the RunPod pod to test every step of:
  1. Azure Blob connectivity
  2. Share Gradients  (check pending files → upload to Azure Blob)
  3. Global Update    (discover versions → download → FedAvg → quantize → upload)

Usage:
  # Full diagnostic (no data is modified)
  python /workspace/ai-ml/test_federated.py --mode check

  # Run only Global Update end-to-end (WRITES a new version to Azure Blob)
  python /workspace/ai-ml/test_federated.py --mode global-update

  # Run only Share Gradients (WRITES pending local weights to Azure Blob)
  python /workspace/ai-ml/test_federated.py --mode share-gradients

  # Run all checks then Global Update
  python /workspace/ai-ml/test_federated.py --mode full
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging setup — timestamp + level + message, written to stdout AND a file
# ---------------------------------------------------------------------------
LOG_FILE = Path("/workspace/logs/federated_test.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8"),
    ],
)

# Suppress noisy Azure SDK / urllib3 HTTP-level debug spam
for _noisy in (
    "azure",
    "azure.core",
    "azure.core.pipeline",
    "azure.storage",
    "azure.storage.blob",
    "urllib3",
    "urllib3.connectionpool",
    "http.client",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

log = logging.getLogger("fed_test")


def section(title: str) -> None:
    bar = "─" * 60
    log.info("")
    log.info(bar)
    log.info(f"  {title}")
    log.info(bar)


def ok(msg: str) -> None:
    log.info(f"  ✓  {msg}")


def fail(msg: str) -> None:
    log.error(f"  ✗  {msg}")


def warn(msg: str) -> None:
    log.warning(f"  ⚠  {msg}")


def info(msg: str) -> None:
    log.info(f"     {msg}")


# ---------------------------------------------------------------------------
# Step 1 — Environment variables
# ---------------------------------------------------------------------------
def check_env() -> bool:
    section("STEP 1 — Environment Variables")
    required = {
        "AZURE_BLOB_ACCOUNT_URL": os.getenv("AZURE_BLOB_ACCOUNT_URL", ""),
        "AZURE_BLOB_SAS_TOKEN":   os.getenv("AZURE_BLOB_SAS_TOKEN", ""),
        "AZURE_BLOB_CONTAINER":   os.getenv("AZURE_BLOB_CONTAINER", ""),
        "STORAGE_BACKEND":        os.getenv("STORAGE_BACKEND", ""),
    }
    all_ok = True
    for key, val in required.items():
        if val:
            ok(f"{key} = {val[:40]}{'...' if len(val) > 40 else ''}")
        else:
            fail(f"{key} is NOT set — federated learning will fail silently")
            all_ok = False

    backend = os.getenv("STORAGE_BACKEND", "")
    if backend and backend.lower() != "azure":
        warn(f"STORAGE_BACKEND={backend!r} — expected 'azure' for Azure Blob")

    dotenv_path = Path("/workspace/ai-ml/.env")
    if dotenv_path.exists():
        info(f".env found at {dotenv_path}")
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path, override=False)
            ok("Loaded .env")
        except ImportError:
            warn("python-dotenv not installed — .env not loaded")
    else:
        warn(f"No .env at {dotenv_path} — using shell exports only")

    return all_ok


# ---------------------------------------------------------------------------
# Step 2 — Python packages
# ---------------------------------------------------------------------------
def check_packages() -> bool:
    section("STEP 2 — Required Python Packages")
    packages = {
        "torch":                "PyTorch (FedAvg weight averaging)",
        "safetensors":          "SafeTensors (shard read/write)",
        "azure.storage.blob":   "Azure Blob SDK",
        "transformers":         "HuggingFace Transformers",
        "peft":                 "PEFT / LoRA",
        "trl":                  "TRL (SFTTrainer)",
        "accelerate":           "Accelerate",
        "bitsandbytes":         "BitsAndBytes (quantization)",
        "datasets":             "HuggingFace Datasets",
        "einops":               "Einops (Qwen2-VL vision encoder)",
    }
    all_ok = True
    for pkg, desc in packages.items():
        try:
            mod = __import__(pkg.replace(".", "_").split("_")[0])
            ver = getattr(mod, "__version__", "?")
            # special case for sub-packages
            if "." in pkg:
                parts = pkg.split(".")
                sub = __import__(pkg, fromlist=[parts[-1]])
                ver = getattr(sub, "__version__", ver)
            ok(f"{pkg}=={ver}   ({desc})")
        except ImportError as e:
            fail(f"{pkg} NOT INSTALLED — {desc} — {e}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Step 3 — Azure Blob connectivity
# ---------------------------------------------------------------------------
def check_azure_blob() -> Optional[Any]:
    section("STEP 3 — Azure Blob Storage Connectivity")
    try:
        sys.path.insert(0, "/workspace/ai-ml")
        from fine_tuning.storage_client import get_storage_client
        client = get_storage_client()
        ok(f"Storage client: {type(client).__name__}")
        info(f"Endpoint : {getattr(client, '_endpoint', 'N/A')}")
        info(f"Container: {getattr(client, '_bucket', 'N/A')}")
    except Exception as e:
        fail(f"Failed to create storage client: {e}")
        log.debug(traceback.format_exc())
        return None

    configured = getattr(client, "_configured", True)
    if not configured:
        fail("Client is not configured — AZURE_BLOB_ACCOUNT_URL or AZURE_BLOB_SAS_TOKEN is empty")
        return None

    try:
        client.probe()
        ok("Container is reachable (probe passed)")
    except Exception as e:
        fail(f"Container probe FAILED: {e}")
        log.debug(traceback.format_exc())
        return None

    return client


# ---------------------------------------------------------------------------
# Step 4 — Discover fine-tuned versions in Azure Blob
# ---------------------------------------------------------------------------
def check_versions(client: Any) -> Optional[int]:
    section("STEP 4 — Version Discovery in Azure Blob")
    try:
        latest = client.get_latest_finetuned_version()
        if latest is None:
            fail("finetuned/latest.txt not found in Azure Blob — no versions uploaded yet")
            info("Run fix_blob_paths.py first, or complete a Local Training + Share Gradients cycle")
            return None
        ok(f"finetuned/latest.txt → v{latest}")
    except Exception as e:
        fail(f"get_latest_finetuned_version() raised: {e}")
        log.debug(traceback.format_exc())
        return None

    try:
        versions = client.list_finetuned_versions(latest, count=10)
        ok(f"Available versions: {versions}")
        return latest
    except Exception as e:
        fail(f"list_finetuned_versions() raised: {e}")
        log.debug(traceback.format_exc())
        return latest


# ---------------------------------------------------------------------------
# Step 5 — Download a single version (read-only connectivity test)
# ---------------------------------------------------------------------------
def check_download(client: Any, latest: int) -> Optional[str]:
    section(f"STEP 5 — Download v{latest} from Azure Blob (connectivity test)")
    tmp_dir = tempfile.mkdtemp(prefix="fed_dl_test_")
    try:
        t0 = time.time()
        local = client.download_finetuned_model(latest, tmp_dir)
        elapsed = time.time() - t0
        files = list(Path(local).rglob("*"))
        total_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1e6
        ok(f"Downloaded {len([f for f in files if f.is_file()])} files ({total_mb:.1f} MB) in {elapsed:.1f}s")
        for f in sorted(files):
            if f.is_file():
                info(f"  {f.relative_to(tmp_dir)}  ({f.stat().st_size // 1024} KB)")
        # Verify HF model structure
        has_config   = (Path(local) / "config.json").exists()
        has_safetens = bool(list(Path(local).glob("*.safetensors")))
        if has_config:
            ok("config.json present ✓")
        else:
            fail("config.json MISSING — HF model loading will fail")
        if has_safetens:
            ok(f"safetensors shards present ({len(list(Path(local).glob('*.safetensors')))} files) ✓")
        else:
            fail("No .safetensors files found — FedAvg cannot average weights")
        return local if (has_config and has_safetens) else None
    except Exception as e:
        fail(f"Download FAILED: {e}")
        log.debug(traceback.format_exc())
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None


# ---------------------------------------------------------------------------
# Step 6 — FedAvg dry-run (average the single version with itself as smoke test)
# ---------------------------------------------------------------------------
def check_fedavg(model_dir: str) -> bool:
    section("STEP 6 — FedAvg Dry-Run (average model with itself)")
    tmp_out = tempfile.mkdtemp(prefix="fed_avg_test_")
    try:
        sys.path.insert(0, "/workspace/ai-ml")
        from server import _fedavg_safetensors
        t0 = time.time()
        _fedavg_safetensors([model_dir, model_dir], tmp_out)
        elapsed = time.time() - t0
        out_files = list(Path(tmp_out).rglob("*"))
        out_mb = sum(f.stat().st_size for f in out_files if f.is_file()) / 1e6
        ok(f"FedAvg produced {len([f for f in out_files if f.is_file()])} files ({out_mb:.1f} MB) in {elapsed:.1f}s")
        has_config = (Path(tmp_out) / "config.json").exists()
        has_shards = bool(list(Path(tmp_out).glob("*.safetensors")))
        if has_config and has_shards:
            ok("Output structure is valid (config.json + safetensors present)")
            return True
        else:
            fail(f"Output invalid: config.json={has_config}, safetensors={has_shards}")
            return False
    except ImportError:
        warn("Could not import _fedavg_safetensors from server — testing directly")
        try:
            from safetensors import safe_open
            from safetensors.torch import save_file
            import torch
            shards = list(Path(model_dir).glob("*.safetensors"))
            if not shards:
                warn("No safetensors shards — skipping FedAvg test")
                return True
            shard = shards[0]
            all_t: Dict[str, list] = {}
            with safe_open(str(shard), framework="pt") as f:
                for key in f.keys():
                    all_t[key] = [f.get_tensor(key), f.get_tensor(key)]
            averaged = {k: torch.stack(vs).mean(0) for k, vs in all_t.items()}
            save_file(averaged, str(Path(tmp_out) / shard.name))
            ok(f"Direct FedAvg test passed — averaged {len(averaged)} tensors from {shard.name}")
            return True
        except Exception as e:
            fail(f"FedAvg direct test failed: {e}")
            log.debug(traceback.format_exc())
            return False
    except Exception as e:
        fail(f"FedAvg dry-run FAILED: {e}")
        log.debug(traceback.format_exc())
        return False
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


# ---------------------------------------------------------------------------
# Step 7 — Check pending Share Gradients files
# ---------------------------------------------------------------------------
def check_pending_shares() -> List[tuple]:
    section("STEP 7 — Pending Share Gradients Files")
    pending_dir = Path("/workspace/fine_tuning/pending_shares")
    if not pending_dir.exists():
        warn(f"{pending_dir} does not exist — no local training completed yet")
        return []

    pending_files = sorted(pending_dir.glob("*.json"))
    if not pending_files:
        warn("No pending share files found — run Local Training first to generate weights")
        return []

    entries = []
    for fp in pending_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            version  = data.get("version", "?")
            job_id   = data.get("job_id", "?")
            merged   = data.get("merged_model_path", "")
            adapter  = data.get("adapter_path", "")

            info(f"Found: {fp.name}")
            info(f"  version={version}  job_id={job_id[:8]}...")
            info(f"  merged_model_path: {merged}")
            info(f"  adapter_path:      {adapter}")

            merged_ok  = merged and Path(merged).exists()
            adapter_ok = adapter and Path(adapter).exists()

            if merged_ok:
                ok(f"  merged_model_path exists on disk ✓")
            else:
                fail(f"  merged_model_path MISSING on disk — Share Gradients will fail")
            if adapter_ok:
                ok(f"  adapter_path exists on disk ✓")
            else:
                fail(f"  adapter_path MISSING on disk — Share Gradients will fail")

            entries.append((fp, data))
        except Exception as e:
            fail(f"Cannot read {fp.name}: {e}")

    if entries:
        ok(f"{len(entries)} pending version(s) ready to share: "
           f"{[e[1].get('version') for e in entries]}")
    return entries


# ---------------------------------------------------------------------------
# Full Global Update pipeline
# ---------------------------------------------------------------------------
def run_global_update(client: Any) -> bool:
    section("RUNNING GLOBAL UPDATE (FedAvg → Upload)")
    import shutil as _shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="fedavg_run_"))
    try:
        # 1. Discover
        info("Phase 1: discovering versions…")
        latest = client.get_latest_finetuned_version()
        if latest is None:
            fail("No fine-tuned versions in Azure Blob — cannot run Global Update")
            return False
        ok(f"Latest version: {latest}")

        try:
            versions = client.list_finetuned_versions(latest, count=10)
        except Exception as e:
            warn(f"list_finetuned_versions failed ({e}) — using [{latest}]")
            versions = [latest]
        ok(f"Versions to aggregate: {versions}")

        # 2. Download
        info("Phase 2: downloading versions…")
        model_dirs: List[str] = []
        downloaded: List[int] = []
        skipped:    List[int] = []
        for v in versions:
            local_dir = str(tmp_dir / f"v{v}")
            t0 = time.time()
            try:
                client.download_finetuned_model(v, local_dir)
                elapsed = time.time() - t0
                size_mb = sum(f.stat().st_size for f in Path(local_dir).rglob("*") if f.is_file()) / 1e6
                ok(f"Downloaded v{v} — {size_mb:.0f} MB in {elapsed:.1f}s")
                model_dirs.append(local_dir)
                downloaded.append(v)
            except Exception as dl_err:
                fail(f"Download v{v} FAILED: {dl_err}")
                log.debug(traceback.format_exc())
                skipped.append(v)

        if not model_dirs:
            fail(f"All versions failed to download. Cannot proceed.")
            return False
        if skipped:
            warn(f"Skipped {skipped} — proceeding with {downloaded}")

        # 3. FedAvg
        info("Phase 3: FedAvg aggregation…")
        agg_dir = str(tmp_dir / "aggregated")
        try:
            sys.path.insert(0, "/workspace/ai-ml")
            from server import _fedavg_safetensors
            t0 = time.time()
            _fedavg_safetensors(model_dirs, agg_dir)
            ok(f"FedAvg complete in {time.time() - t0:.1f}s → {agg_dir}")
        except Exception as e:
            fail(f"FedAvg FAILED: {e}")
            log.debug(traceback.format_exc())
            return False

        if not (Path(agg_dir) / "config.json").exists():
            fail("Aggregated model missing config.json — aborting upload")
            return False
        ok("Aggregated model structure valid (config.json present)")

        # 4. Quantize (non-fatal)
        info("Phase 4: quantization (non-fatal if tools unavailable)…")
        gguf_dir = str(tmp_dir / "gguf")
        quant_results: Dict = {}
        try:
            from fine_tuning.quantization.quantizer import run_quantization
            quant_results = run_quantization(agg_dir, gguf_dir, latest + 1)
            ok(f"Quantization produced {len(quant_results)} GGUF(s): {list(quant_results.keys())}")
        except Exception as e:
            warn(f"Quantization skipped (non-fatal): {e}")

        # 5. Upload
        new_version = latest + 1
        info(f"Phase 5: uploading aggregated model as v{new_version}…")
        t0 = time.time()
        try:
            client.upload_hf_model(agg_dir, new_version)
            ok(f"HF model uploaded as v{new_version} in {time.time() - t0:.1f}s")
        except Exception as e:
            fail(f"upload_hf_model FAILED: {e}")
            log.debug(traceback.format_exc())
            return False

        if quant_results:
            try:
                keys = client.upload_quantized(gguf_dir, new_version)
                ok(f"GGUFs uploaded: {keys}")
            except Exception as e:
                warn(f"GGUF upload failed (non-fatal): {e}")

        # 6. Verify
        info("Phase 6: verifying new version is discoverable…")
        new_latest = client.get_latest_finetuned_version()
        if new_latest == new_version:
            ok(f"finetuned/latest.txt updated to v{new_version} ✓")
        else:
            warn(f"latest.txt shows v{new_latest}, expected v{new_version}")

        section(f"GLOBAL UPDATE COMPLETE — v{new_version} is now in Azure Blob")
        return True

    except Exception as e:
        fail(f"Global Update pipeline FAILED: {e}")
        log.debug(traceback.format_exc())
        return False
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)
        info(f"Cleaned up temp dir: {tmp_dir}")


# ---------------------------------------------------------------------------
# Share Gradients pipeline
# ---------------------------------------------------------------------------
def run_share_gradients(client: Any) -> bool:
    section("RUNNING SHARE GRADIENTS")
    entries = check_pending_shares()
    if not entries:
        warn("Nothing to share — no pending local weights found")
        return False

    try:
        sys.path.insert(0, "/workspace/ai-ml")
        from fine_tuning.training_orchestrator import promote_adapter
    except Exception as e:
        fail(f"Cannot import promote_adapter: {e}")
        log.debug(traceback.format_exc())
        return False

    all_ok = True
    for file_path, pending in entries:
        version = pending.get("version", "?")
        info(f"Uploading v{version}…")
        try:
            merged = pending.get("merged_model_path", "")
            adapter = pending.get("adapter_path", "")
            if not merged or not Path(merged).exists():
                fail(f"v{version}: merged_model_path missing or not on disk: '{merged}'")
                all_ok = False
                continue
            if not adapter or not Path(adapter).exists():
                fail(f"v{version}: adapter_path missing or not on disk: '{adapter}'")
                all_ok = False
                continue

            t0 = time.time()
            promote_adapter(
                adapter_id=pending["job_id"],
                registry_path=pending["registry_path"],
                version=pending["version"],
                merged_model_path=pending["merged_model_path"],
                adapter_path=pending["adapter_path"],
                eval_scores=pending.get("eval_scores", {}),
                training_meta=pending.get("training_meta", {}),
                base_model=pending.get("base_model", ""),
            )
            ok(f"v{version} uploaded in {time.time() - t0:.1f}s")
            file_path.unlink(missing_ok=True)
            ok(f"v{version} pending-share manifest deleted")
        except Exception as e:
            fail(f"v{version} upload FAILED: {e}")
            log.debug(traceback.format_exc())
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Federated learning diagnostic & test runner")
    parser.add_argument(
        "--mode",
        choices=["check", "global-update", "share-gradients", "full"],
        default="check",
        help=(
            "check          — read-only diagnostics only (default)\n"
            "global-update  — run full FedAvg pipeline (WRITES to Azure Blob)\n"
            "share-gradients— upload pending local weights to Azure Blob\n"
            "full           — check + global-update"
        ),
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    log.info(f"Federated Learning Test  |  mode={args.mode}  |  started={started_at}")
    log.info(f"Log file: {LOG_FILE}")

    # Load .env if present
    env_path = Path("/workspace/ai-ml/.env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except ImportError:
            pass

    results: Dict[str, bool] = {}

    # Always run checks
    results["env"]      = check_env()
    results["packages"] = check_packages()
    client              = check_azure_blob()
    results["azure"]    = client is not None

    if client is None:
        fail("Azure Blob unreachable — stopping here. Fix env vars and retry.")
        _print_summary(results)
        sys.exit(1)

    latest = check_versions(client)
    results["versions"] = latest is not None

    if latest is not None:
        model_dir = check_download(client, latest)
        results["download"] = model_dir is not None
        if model_dir:
            results["fedavg"] = check_fedavg(model_dir)
            shutil.rmtree(Path(model_dir).parent, ignore_errors=True)
    else:
        warn("Skipping download and FedAvg checks — no versions available")

    results["pending"] = bool(check_pending_shares())

    # Run pipelines if requested
    if args.mode in ("global-update", "full"):
        if latest is None:
            fail("Cannot run Global Update — no versions found in Azure Blob")
        else:
            results["global_update"] = run_global_update(client)

    if args.mode == "share-gradients":
        results["share_gradients"] = run_share_gradients(client)

    _print_summary(results)
    failed = [k for k, v in results.items() if not v]
    sys.exit(0 if not failed else 1)


def _print_summary(results: Dict[str, bool]) -> None:
    section("SUMMARY")
    for step, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗"
        log.info(f"  {step:<22} {status}")
    failed = [k for k, v in results.items() if not v]
    if not failed:
        ok("All checks passed")
    else:
        fail(f"Failed steps: {failed}")
    log.info(f"\nFull log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
