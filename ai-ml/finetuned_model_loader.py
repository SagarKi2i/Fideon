"""
Download the latest fine-tuned (non-quantized) HF model from Azure Blob Storage.

Use this to test the fine-tuned model WITHOUT quantization — i.e. confirm
whether a bad model is broken before or after quantization.

Flow:
  1. Connect to Azure Blob (same AzureBlobClient used by the training pipeline)
  2. Discover the latest promoted version via finetuned/latest.txt
  3. Download all files from  finetuned/v{N}/  →  /workspace/models/finetuned/v{N}/
  4. Print the path — set QWEN_MODEL_ID to this path, USE_OLLAMA=false to use it

Usage:
    python finetuned_model_loader.py                 # download latest version
    python finetuned_model_loader.py --version 26    # specific version
    python finetuned_model_loader.py --skip-if-loaded  # no-op if already on disk

Required env vars (same as AzureBlobClient):
    AZURE_BLOB_ACCOUNT_URL
    AZURE_BLOB_SAS_TOKEN
    AZURE_BLOB_CONTAINER   (default: fideon-models)

Optional:
    FINETUNED_MODEL_DIR    (default: /workspace/models/finetuned)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

FINETUNED_DIR = Path(os.getenv("FINETUNED_MODEL_DIR", "/workspace/models/finetuned"))

# Written on successful download so startup.sh can read the path without
# re-querying Azure Blob on every pod restart.
_PATH_FILE = FINETUNED_DIR / "loaded_path.txt"


def _log(msg: str) -> None:
    print(f"[finetuned_loader] {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"[finetuned_loader] ERROR: {msg}", flush=True, file=sys.stderr)


def _get_storage_client():
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


def _already_downloaded(version: int) -> bool:
    """Return True if the version directory exists and contains at least one safetensors file."""
    dest = FINETUNED_DIR / f"v{version}"
    return dest.exists() and any(dest.glob("*.safetensors"))


def download_finetuned(version: int, force: bool = False) -> Path:
    """
    Download finetuned/v{version}/ from Azure Blob → FINETUNED_DIR/v{version}/.
    Returns the local directory path.
    """
    client = _get_storage_client()

    if not client._configured:
        raise RuntimeError(
            "Azure Blob is not configured. "
            "Set AZURE_BLOB_ACCOUNT_URL and AZURE_BLOB_SAS_TOKEN env vars."
        )

    dest_dir = FINETUNED_DIR / f"v{version}"

    if not force and _already_downloaded(version):
        _log(f"v{version} already on disk at {dest_dir} — skipping download (use --force to re-download)")
        return dest_dir

    _log(f"Downloading finetuned/v{version}/ → {dest_dir} …")
    dest_dir.mkdir(parents=True, exist_ok=True)

    def _progress(rel: str, downloaded: int, total: Optional[int]) -> None:
        if total:
            pct = int(downloaded * 100 / total)
            print(f"\r  {rel}: {pct}%", end="", flush=True)

    client.download_finetuned_model(version, str(dest_dir), progress_callback=_progress)
    print()  # newline after progress
    _log(f"Download complete → {dest_dir}")

    # Write loaded_path.txt so startup.sh can export QWEN_MODEL_ID without a
    # second Azure Blob round-trip on every pod restart.
    _PATH_FILE.write_text(str(dest_dir))

    return dest_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download fine-tuned HF model (non-quantized) from Azure Blob"
    )
    parser.add_argument("--version", type=int, default=None,
                        help="Model version to download (default: latest)")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if model already on disk")
    parser.add_argument("--skip-if-loaded", action="store_true",
                        help="No-op if the version is already downloaded")
    args = parser.parse_args()

    client = _get_storage_client()
    version = _discover_version(client, args.version)

    if args.skip_if_loaded and _already_downloaded(version):
        dest = FINETUNED_DIR / f"v{version}"
        _log(f"v{version} already on disk — nothing to do.")
        _log(f"To use it:  export QWEN_MODEL_ID={dest}  USE_OLLAMA=false")
        # Refresh the path file so startup.sh always finds the current version.
        FINETUNED_DIR.mkdir(parents=True, exist_ok=True)
        _PATH_FILE.write_text(str(dest))
        return

    dest_dir = download_finetuned(version, force=args.force)

    _log("─" * 60)
    _log(f"Fine-tuned HF model v{version} ready at: {dest_dir}")
    _log("")
    _log("To run extraction through this model (no quantization):")
    _log(f"  export QWEN_MODEL_ID={dest_dir}")
    _log(f"  export USE_OLLAMA=false")
    _log("")
    _log("This runs the full fine-tuned weights through the HF transformers")
    _log("stack — same path as the base model, but with fine-tuned weights.")


if __name__ == "__main__":
    main()
