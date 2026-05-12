"""
Storage client factory — always returns AzureBlobClient.

All clients expose the same interface:
  - probe()
  - upload_hf_model(local_dir, version, progress_callback=None) -> str
  - download_finetuned_model(version, local_dir, progress_callback=None) -> str
  - upload_quantized(gguf_dir, version, progress_callback=None) -> List[str]
  - get_latest_finetuned_version() -> Optional[int]
  - list_finetuned_versions(latest, count) -> List[int]
"""
from __future__ import annotations


def get_storage_client():
    from fine_tuning.azure_blob_client import AzureBlobClient
    return AzureBlobClient()
