"""
Thin factory: returns the configured storage client.

Currently always returns SeaweedFSClient. If a second backend is added later,
read STORAGE_BACKEND env var here and branch accordingly.
"""
from __future__ import annotations

from fine_tuning.seaweedfs_client import SeaweedFSClient


def get_storage_client() -> SeaweedFSClient:
    """Return the active storage client (SeaweedFS)."""
    return SeaweedFSClient()
