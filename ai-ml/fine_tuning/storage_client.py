"""
Storage backend factory.

Set STORAGE_BACKEND=azure  to use Azure Blob Storage.
Set STORAGE_BACKEND=seaweedfs  (or leave unset) to use SeaweedFS (default).
"""
from __future__ import annotations
import os


def get_storage_client():
    """Return the configured storage client (AzureBlobClient or SeaweedFSClient)."""
    backend = os.getenv("STORAGE_BACKEND", "azure").strip().lower()
    if backend == "seaweedfs":
        from fine_tuning.seaweedfs_client import SeaweedFSClient
        return SeaweedFSClient()
    from fine_tuning.azure_blob_client import AzureBlobClient
    return AzureBlobClient()
