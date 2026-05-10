"""
Download the latest quantized GGUF from Azure Blob Storage and load it into Ollama.

Flow:
  1. Connect to Azure Blob (same AzureBlobClient used by the training pipeline)
  2. Discover the latest promoted version via finetuned/latest.txt
  3. Download all *.gguf files from  quantized/v{N}/  →  /workspace/models/gguf/
  4. Pick the best quant (Q5_K_M > Q4_K_M > first available)
  5. Write a Modelfile for Ollama
  6. Run: ollama create fideon-acord -f <Modelfile>

Usage:
    python model_loader.py                 # auto-select latest version
    python model_loader.py --version 3     # specific version
    python model_loader.py --force         # re-download even if GGUF already on disk
    python model_loader.py --dry-run       # download only, don't load into Ollama

Required env vars (same as AzureBlobClient):
    AZURE_BLOB_ACCOUNT_URL
    AZURE_BLOB_SAS_TOKEN
    AZURE_BLOB_CONTAINER   (default: fideon-models)

Optional:
    OLLAMA_MODEL_NAME      (default: fideon-acord)
    OLLAMA_HOST            (default: http://localhost:11434)
    GGUF_DIR               (default: /workspace/models/gguf)
    OLLAMA_NUM_CTX         (default: 8192)
    OLLAMA_TEMPERATURE     (default: 0.1)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

GGUF_DIR        = Path(os.getenv("GGUF_DIR",         "/workspace/models/gguf"))
OLLAMA_HOST     = os.getenv("OLLAMA_HOST",            "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL_NAME",      "fideon-acord")
OLLAMA_NUM_CTX  = int(os.getenv("OLLAMA_NUM_CTX",    "8192"))
OLLAMA_TEMP     = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))

# Preference order for quant level — ordered by inference speed / VRAM footprint, not raw quality.
# Q8_0 ranks last among integer quants because it is 2× the size of Q5_K_M with marginal quality
# gain for ACORD extraction; use --force + rename to override if quality-first is needed.
_QUANT_PRIORITY = ["q5_k_m", "q4_k_m", "q5_0", "q4_0", "q8_0", "f16"]

SYSTEM_PROMPT = (
    "You are an expert insurance document parser. "
    "Extract all fields from ACORD insurance forms exactly as instructed. "
    "Always respond in the structured format requested — no commentary."
)


# ── Logging ──────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[model_loader] {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"[model_loader] ERROR: {msg}", flush=True, file=sys.stderr)


# ── Azure Blob: download GGUFs ───────────────────────────────────────────────

def _get_storage_client():
    """Re-use the same AzureBlobClient that the training pipeline uses."""
    sys.path.insert(0, str(Path(__file__).parent))
    from fine_tuning.storage_client import get_storage_client
    return get_storage_client()


def _discover_version(client, requested: Optional[int]) -> int:
    if requested is not None:
        _log(f"Using requested version: v{requested}")
        return requested
    latest = client.get_latest_finetuned_version()
    if latest is None:
        raise RuntimeError(
            "No fine-tuned version found in Azure Blob (finetuned/latest.txt missing). "
            "Run Local Training → Global Update first to promote a model version."
        )
    _log(f"Latest promoted version: v{latest}")
    return latest


def download_gguf(version: int, force: bool = False) -> Path:
    """
    Download all *.gguf files for the given version from Azure Blob
    quantized/v{N}/ → GGUF_DIR/v{N}/.

    Returns the path to the best GGUF file.
    """
    client = _get_storage_client()

    if not client._configured:
        raise RuntimeError(
            "Azure Blob is not configured. "
            "Set AZURE_BLOB_ACCOUNT_URL and AZURE_BLOB_SAS_TOKEN env vars."
        )

    dest_dir = GGUF_DIR / f"v{version}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"quantized/v{version}/"
    _log(f"Scanning Azure Blob: {client._container}/{prefix}")

    try:
        cc = client._container_client()
        blobs = [b for b in cc.list_blobs(name_starts_with=prefix)]
    except Exception as exc:
        raise RuntimeError(
            f"Cannot list blobs at {client._account_url}/{client._container}/{prefix}: {exc}"
        ) from exc

    gguf_blobs = [b for b in blobs if str(b["name"]).endswith(".gguf")]
    if not gguf_blobs:
        raise RuntimeError(
            f"No *.gguf files found at {client._container}/{prefix}. "
            "Run the fine-tuning pipeline to produce quantized GGUF artifacts first."
        )

    _RETRY_DELAYS = [30, 60, 120, 240]

    downloaded: list[Path] = []
    for blob_props in gguf_blobs:
        blob_name  = blob_props["name"]
        filename   = Path(blob_name).name
        dest_path  = dest_dir / filename
        size_mb    = (blob_props.get("size") or 0) // 1_000_000

        if dest_path.exists() and not force:
            _log(f"  {filename} ({size_mb} MB) — already on disk, skipping")
            downloaded.append(dest_path)
            continue

        _log(f"  Downloading {filename} ({size_mb} MB) …")
        # Write to a temp file and rename only on success so a failed/partial
        # download never looks like a complete file on the next startup.
        tmp_path = dest_path.with_suffix(".gguf.tmp")
        last_exc: Optional[Exception] = None
        for attempt in range(1, 6):
            try:
                blob_client = cc.get_blob_client(blob_name)
                downloader  = blob_client.download_blob(max_concurrency=4)
                with open(tmp_path, "wb") as fh:
                    for chunk in downloader.chunks():
                        fh.write(chunk)
                tmp_path.rename(dest_path)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                tmp_path.unlink(missing_ok=True)
                if attempt < 5:
                    import random
                    wait = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
                    wait += random.randint(0, 15)
                    _err(f"  Retry {attempt}/5 for {filename} in {wait}s: {exc}")
                    time.sleep(wait)

        if last_exc is not None:
            _err(f"  Failed to download {filename} after 5 attempts: {last_exc}")
        else:
            _log(f"  {filename} ✓")
            downloaded.append(dest_path)

    if not downloaded:
        raise RuntimeError(f"All GGUF downloads failed for version v{version}.")

    best = _pick_best_gguf(downloaded)
    _log(f"Selected GGUF: {best.name}")
    return best


def _pick_best_gguf(paths: list[Path]) -> Path:
    """Return the highest-quality GGUF from a list based on _QUANT_PRIORITY."""
    name_map = {p.name.lower(): p for p in paths}
    for quant in _QUANT_PRIORITY:
        for name, path in name_map.items():
            if quant in name:
                return path
    return paths[0]


# ── Ollama: create model from GGUF ──────────────────────────────────────────

def _write_modelfile(gguf_path: Path, modelfile_path: Path) -> None:
    """Write an Ollama Modelfile pointing at the local GGUF."""
    content = f"""\
FROM {gguf_path}

PARAMETER temperature {OLLAMA_TEMP}
PARAMETER num_ctx {OLLAMA_NUM_CTX}
PARAMETER num_predict 4096

SYSTEM \"\"\"{SYSTEM_PROMPT}\"\"\"
"""
    modelfile_path.write_text(content)
    _log(f"Modelfile written to {modelfile_path}")


def _ollama_ready(timeout: int = 30) -> bool:
    """Wait until Ollama HTTP API is responding."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3)
            return True
        except Exception:
            time.sleep(2)
    return False


def load_into_ollama(gguf_path: Path) -> str:
    """
    Create (or overwrite) the Ollama model from the GGUF.
    Returns the model name registered in Ollama.
    """
    modelfile_path = gguf_path.parent / "Modelfile.fideon"
    _write_modelfile(gguf_path, modelfile_path)

    _log(f"Waiting for Ollama at {OLLAMA_HOST} …")
    if not _ollama_ready(timeout=60):
        raise RuntimeError(
            f"Ollama is not responding at {OLLAMA_HOST} after 60s. "
            "Make sure 'ollama serve' is running before calling model_loader.py."
        )
    _log("Ollama is ready.")

    _log(f"Running: ollama create {OLLAMA_MODEL} -f {modelfile_path}")
    env = os.environ.copy()
    env["OLLAMA_HOST"] = OLLAMA_HOST
    result = subprocess.run(
        ["ollama", "create", OLLAMA_MODEL, "-f", str(modelfile_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ollama create failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    _log(f"Model '{OLLAMA_MODEL}' loaded into Ollama successfully.")
    _log(f"stdout: {result.stdout.strip()}")
    return OLLAMA_MODEL


# ── Version tracking ──────────────────────────────────────────────────────────
# Written on every successful ollama create so pod restarts can detect when a
# newer version has been promoted to finetuned/latest.txt without re-querying
# Azure Blob for every startup.

_VERSION_FILE = GGUF_DIR / "loaded_version.txt"


def _write_loaded_version(version: int) -> None:
    GGUF_DIR.mkdir(parents=True, exist_ok=True)
    _VERSION_FILE.write_text(str(version))


def _read_loaded_version() -> Optional[int]:
    try:
        return int(_VERSION_FILE.read_text().strip())
    except Exception:
        return None


# ── Status check ─────────────────────────────────────────────────────────────

def _model_up_to_date(latest_version: int) -> bool:
    """
    Return True only if:
      1. fideon-acord is present in Ollama's registry, AND
      2. the on-disk loaded_version.txt matches latest_version.
    If either condition fails, the caller must re-download and re-register.
    """
    import urllib.request, json as _json

    loaded_ver = _read_loaded_version()
    if loaded_ver != latest_version:
        _log(f"Version mismatch: loaded=v{loaded_ver}  latest=v{latest_version} — will reload")
        return False

    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            data = _json.loads(resp.read())
            names = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            if OLLAMA_MODEL in names:
                return True
    except Exception:
        pass

    _log(f"Model '{OLLAMA_MODEL}' not found in Ollama registry — will reload")
    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Download GGUF from Azure Blob and load into Ollama")
    parser.add_argument("--version",  type=int, default=None, help="Model version to download (default: latest)")
    parser.add_argument("--force",    action="store_true",    help="Re-download even if GGUF already on disk")
    parser.add_argument("--dry-run",  action="store_true",    help="Download only — do not load into Ollama")
    parser.add_argument("--skip-if-loaded", action="store_true",
                        help="Skip if the currently loaded version matches the latest in Azure Blob")
    args = parser.parse_args()

    client = _get_storage_client()
    version = _discover_version(client, args.version)

    if args.skip_if_loaded and _model_up_to_date(version):
        _log(f"Model '{OLLAMA_MODEL}' v{version} already loaded — nothing to do.")
        return

    _log(f"Downloading GGUF for v{version} → {GGUF_DIR}/v{version}/")
    gguf_path = download_gguf(version, force=args.force)

    if args.dry_run:
        _log(f"Dry-run: GGUF downloaded at {gguf_path}. Skipping ollama create.")
        return

    model_name = load_into_ollama(gguf_path)
    _write_loaded_version(version)
    _log(f"Done. Use model name: '{model_name}' (v{version})")


if __name__ == "__main__":
    main()
