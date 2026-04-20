"""
Device admin endpoints — replaces direct frontend Supabase calls for:
  - Pending device management (PendingDevices.tsx)
  - Device model allocation (DeviceDetails.tsx)
  - Device token regeneration (DeviceDetails.tsx)
  - Admin device-pairings list (AdminDashboard.tsx)
"""
import hashlib
import json
import secrets
from typing import List, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import (
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
    verify_admin,
    verify_user,
)

router = APIRouter()


async def _admin_uid(authorization: Optional[str]) -> str:
    user = await verify_admin(authorization)
    uid = user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return uid


# ═══════════════════════════════════════════════════════════════════════════════
# PENDING DEVICES (never_checked_in)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/admin/pending-devices")
async def list_pending_devices(authorization: Optional[str] = Header(default=None)):
    """Return devices with status=never_checked_in (admin only)."""
    await _admin_uid(authorization)
    rows = await postgrest_get(
        "devices",
        (
            "select=id,device_name,device_token,os_type,registered_at,metadata"
            "&status=eq.never_checked_in"
            "&order=registered_at.desc"
        ),
    )
    return {"devices": rows}


@router.patch("/api/v1/admin/pending-devices/{device_id}/approve")
async def approve_pending_device(
    device_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Approve a pending device: set status=offline, is_active=true, create license."""
    await _admin_uid(authorization)

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {"status": "offline", "is_active": True},
    )

    # Create default license (best-effort — ignore if already exists)
    try:
        await postgrest_insert(
            "device_licenses",
            {"device_id": device_id, "license_type": "standard", "status": "active"},
        )
    except Exception:
        pass  # May already exist

    return {"success": True}


@router.patch("/api/v1/admin/pending-devices/{device_id}/reject")
async def reject_pending_device(
    device_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Reject a pending device: set is_active=false."""
    await _admin_uid(authorization)
    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {"is_active": False},
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE MODEL ALLOCATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/v1/admin/devices/{device_id}/models")
async def allocate_device_models(
    device_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Allocate models to a device (admin only)."""
    uid = await _admin_uid(authorization)
    body = await request.json()
    models: List[dict] = body.get("models") or []
    if not models:
        raise HTTPException(status_code=400, detail="models list is required")

    rows_to_insert = [
        {
            "device_id": device_id,
            "model_id": m.get("model_id"),
            "model_name": m.get("model_name") or m.get("model_id"),
            "domain": m.get("domain") or "unknown",
            "allocated_by": uid,
        }
        for m in models
        if m.get("model_id")
    ]
    if not rows_to_insert:
        raise HTTPException(status_code=400, detail="No valid models provided")

    # Insert all in one batch
    headers = service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/device_models",
            headers=headers,
            content=json.dumps(rows_to_insert),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)

    return {"success": True, "allocated": len(rows_to_insert)}


@router.delete("/api/v1/admin/devices/{device_id}/models/{record_id}")
async def remove_device_model(
    device_id: str,
    record_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Remove a model allocation from a device (admin only)."""
    await _admin_uid(authorization)
    await postgrest_delete(
        "device_models",
        f"id=eq.{quote(record_id, safe='')}&device_id=eq.{quote(device_id, safe='')}",
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE TOKEN REGENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/v1/admin/devices/{device_id}/regenerate-token")
async def regenerate_device_token(
    device_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Generate a new device token and reset status to never_checked_in (admin only)."""
    await _admin_uid(authorization)

    # Generate a secure token the same way the DB function does.
    new_token = "nbt_" + secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(new_token.encode("utf-8")).hexdigest()

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {
            "device_token": new_token,
            "token_hash": token_hash,
            "status": "never_checked_in",
        },
    )
    return {"success": True, "device_token": new_token}


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE PAIRINGS (AdminDashboard)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/admin/device-pairings")
async def list_device_pairings(
    limit: int = 12,
    authorization: Optional[str] = Header(default=None),
):
    """Return recent device pairing records (admin only)."""
    await _admin_uid(authorization)
    rows = await postgrest_get(
        "device_pairings",
        (
            "select=id,status,created_at,expires_at,consumed_at,linked_device_id,primary_device_label"
            f"&order=created_at.desc&limit={min(limit, 100)}"
        ),
    )
    return {"device_pairings": rows}


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH AUDIT — write from pod activation approve/reject
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/v1/admin/auth-audit")
async def write_auth_audit(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Insert an auth_audit row for pod approval/rejection events (admin only)."""
    from app.core.supabase import insert_auth_audit_row
    await verify_admin(authorization)
    body = await request.json()
    user_id = str(body.get("user_id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    await insert_auth_audit_row(
        user_id=user_id,
        email=str(body.get("email") or ""),
        role=str(body.get("role") or "admin"),
        event=str(body.get("event") or ""),
        action_code=str(body.get("action_code") or "E"),
        outcome_code=int(body.get("outcome_code") or 0),
        resource_type=str(body.get("resource_type") or ""),
        resource_id=body.get("resource_id"),
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# POD REQUEST USER INFO (PodActivationRequests.tsx requester detail modal)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/admin/pod-request-user/{user_id}")
async def get_pod_request_user(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Return app_user + tenant name for a pod activation request (admin only)."""
    await verify_admin(authorization)
    app_user_rows = await postgrest_get(
        "app_users",
        f"select=full_name,email,tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    if not app_user_rows:
        return {"user": None, "tenant_name": None}

    app_user = app_user_rows[0]
    tenant_name = None
    tenant_id = app_user.get("tenant_id")
    if tenant_id:
        tenant_rows = await postgrest_get(
            "tenants",
            f"select=name&id=eq.{quote(str(tenant_id), safe='')}&limit=1",
        )
        if tenant_rows:
            tenant_name = tenant_rows[0].get("name")

    return {
        "user": {
            "full_name": app_user.get("full_name"),
            "email": app_user.get("email"),
            "tenant_id": tenant_id,
        },
        "tenant_name": tenant_name,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT NAME LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/admin/tenants")
async def list_tenants_by_ids(
    ids: str = "",
    authorization: Optional[str] = Header(default=None),
):
    """Return tenant names for a comma-separated list of tenant IDs (admin only)."""
    await verify_admin(authorization)
    if not ids.strip():
        return {"tenants": []}
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        return {"tenants": []}
    ids_joined = ",".join(quote(i, safe="") for i in id_list)
    rows = await postgrest_get(
        "tenants",
        f"select=id,name&id=in.({ids_joined})",
    )
    return {"tenants": rows}
