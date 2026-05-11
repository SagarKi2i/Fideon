"""
Adapter registry: serve fresh presigned download URLs for GGUF model artifacts.

Electron calls GET /api/v1/adapter/latest    — to check if a new version is available (canary-gated).
Electron calls GET /api/v1/adapter/download-url — to get a fresh 1-hour presigned URL when ready to download.
"""

from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Header, HTTPException

from app.core.config import (
    AZURE_BLOB_ACCOUNT_URL,
    AZURE_BLOB_CONTAINER,
    AZURE_BLOB_SAS_TOKEN,
)
from app.core.supabase import postgrest_get
from app.routes.device import _resolve_device_from_bearer, _load_active_device_row, _enforce_not_revoked

log = structlog.get_logger("adapter_registry")
router = APIRouter()

def _build_download_url(blob_key: str, sig: bool = False) -> str:
    """Return an Azure Blob SAS URL for blob_key (valid for SAS token lifetime)."""
    object_key = f"{blob_key}.sig" if sig else blob_key
    if not (AZURE_BLOB_ACCOUNT_URL and AZURE_BLOB_SAS_TOKEN):
        raise HTTPException(status_code=503, detail="Azure Blob storage is not configured on this server")
    return f"{AZURE_BLOB_ACCOUNT_URL}/{AZURE_BLOB_CONTAINER}/{object_key}?{AZURE_BLOB_SAS_TOKEN}"


def _in_canary_cohort(device_id: str, version: str, canary_pct: int) -> bool:
    """
    Deterministic canary gate: same device always gets same answer for the same version.
    Uses SHA-256(device_id:version) % 100 < canary_pct.
    canary_pct=100 → everyone gets it. canary_pct=0 → no one gets it.
    """
    if canary_pct >= 100:
        return True
    if canary_pct <= 0:
        return False
    digest = hashlib.sha256(f"{device_id}:{version}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return bucket < canary_pct




async def _verify_device(authorization: Optional[str]) -> str:
    """Verify device JWT and return the device_id. Raises 401/403 on failure."""
    device_id, claims = await _resolve_device_from_bearer(authorization)
    device_row = await _load_active_device_row(device_id)
    _enforce_not_revoked(claims, device_row.get("jwt_issued_after"))
    return device_id


@router.get("/api/v1/adapter/latest")
async def get_latest(
    domain: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    Return the latest available adapter version for this device.
    Applies canary_pct gate — returns { available: false } if device not in cohort.

    Auth: Bearer <device_jwt>  (issued by /api/v1/devices/register)

    Query params:
      domain — e.g. "broker"
    """
    device_id = await _verify_device(authorization)

    q = "&".join([
        "select=adapter_version,quant_level,sha256,size_bytes,min_electron_ver,canary_pct,rollback_safe",
        f"domain=eq.{quote(domain, safe='')}",
        "is_available=eq.true",
        "blocked=eq.false",
        "order=adapter_version.desc",
        "limit=10",
    ])
    rows = await postgrest_get("adapter_registry", q)

    if not rows:
        return {"available": False}

    latest_version = rows[0]["adapter_version"]
    canary_pct = int(rows[0].get("canary_pct") or 0)

    if not _in_canary_cohort(device_id, latest_version, canary_pct):
        log.info(
            "adapter_registry.canary_excluded",
            domain=domain,
            version=latest_version,
            device_id=device_id,
            canary_pct=canary_pct,
        )
        return {"available": False}

    artifacts = [
        {
            "quant_level": r["quant_level"],
            "sha256": r["sha256"],
            "size_bytes": r["size_bytes"],
        }
        for r in rows
        if r["adapter_version"] == latest_version
    ]

    log.info(
        "adapter_registry.update_available",
        domain=domain,
        version=latest_version,
        device_id=device_id,
    )
    return {
        "available": True,
        "adapter_version": latest_version,
        "min_electron_ver": rows[0]["min_electron_ver"],
        "rollback_safe": rows[0]["rollback_safe"],
        "artifacts": artifacts,
    }


@router.get("/api/v1/adapter/download-url")
async def get_download_url(
    domain: str,
    version: str,
    quant: str,
    sig: bool = False,
    authorization: Optional[str] = Header(default=None),
):
    """
    Return a fresh 1-hour presigned URL for a GGUF artifact (or its .sig file).

    Auth: Bearer <device_jwt>  (issued by /api/v1/devices/register)

    Query params:
      domain  — e.g. "broker"
      version — e.g. "1.2.0"
      quant   — e.g. "q5_k_m" or "q4_k_m"
      sig     — if true, returns URL for the .sig file instead of the GGUF
    """
    await _verify_device(authorization)

    q = "&".join([
        "select=blob_key,sha256,size_bytes",
        f"domain=eq.{quote(domain, safe='')}",
        f"adapter_version=eq.{quote(version, safe='')}",
        f"quant_level=eq.{quote(quant, safe='')}",
        "is_available=eq.true",
        "blocked=eq.false",
        "limit=1",
    ])
    rows = await postgrest_get("adapter_registry", q)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No available artifact for domain={domain} version={version} quant={quant}",
        )

    row = rows[0]
    blob_key = row.get("blob_key")
    if not blob_key:
        raise HTTPException(status_code=500, detail="Artifact has no blob_key — re-run upload pipeline")

    url = _build_download_url(blob_key, sig=sig)

    log.info(
        "adapter_registry.download_url_issued",
        domain=domain,
        version=version,
        quant=quant,
        sig=sig,
    )
    return {
        "url": url,
        "sha256": row.get("sha256"),
        "size_bytes": row.get("size_bytes"),
    }
