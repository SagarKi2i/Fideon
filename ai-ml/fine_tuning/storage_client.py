"""
Storage client factory.

Reads STORAGE_BACKEND env var (default: "seaweedfs") and returns the
appropriate client. Both clients expose the same interface:
  - probe()
  - upload_hf_model(local_dir, version, progress_callback=None) -> str
  - download_finetuned_model(version, local_dir, progress_callback=None) -> str
  - upload_quantized(gguf_dir, version, progress_callback=None) -> List[str]
  - get_latest_finetuned_version() -> Optional[int]
  - list_finetuned_versions(latest, count) -> List[int]
"""
from __future__ import annotations

import os


def get_storage_client():
    """Return AzureBlobClient or SeaweedFSClient based on STORAGE_BACKEND env var.

    Auto-detection: if STORAGE_BACKEND is not set, uses Azure when
    AZURE_BLOB_ACCOUNT_URL is present, otherwise falls back to SeaweedFS.
    """
    backend = os.getenv("STORAGE_BACKEND", "").strip().lower()
    if not backend:
        # Auto-detect: prefer Azure if its credentials are present
        backend = "azure" if os.getenv("AZURE_BLOB_ACCOUNT_URL") else "seaweedfs"
    if backend == "azure":
        from fine_tuning.azure_blob_client import AzureBlobClient
        return AzureBlobClient()
    else:
        from fine_tuning.seaweedfs_client import SeaweedFSClient
        return SeaweedFSClient()
