import base64
import hashlib
import re
import secrets
from typing import Optional
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import CARRIER_CREDENTIAL_ENCRYPTION_KEY
from app.core.supabase import postgrest_delete, postgrest_get, postgrest_insert, postgrest_patch, verify_user

router = APIRouter()

ADMIN_ROLES = {"admin", "global_admin"}


# ── Encryption helpers ────────────────────────────────────────────────────────

def _fernet() -> Fernet:
    raw = CARRIER_CREDENTIAL_ENCRYPTION_KEY
    if not raw:
        raise RuntimeError("CARRIER_CREDENTIAL_ENCRYPTION_KEY is not set")
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
        return Fernet(key)


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Carrier credential decrypt failed — key mismatch or corrupted data") from exc


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _require_admin(authorization: Optional[str]) -> tuple[dict, str]:
    """Verify JWT and confirm the caller is admin or global_admin. Returns (user, tenant_id)."""
    user = await verify_user(authorization)
    user_id = user.get("id", "")

    role_rows = await postgrest_get(
        "user_roles",
        f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    role = role_rows[0].get("role") if role_rows else None
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions — admin or global_admin required")

    tenant_rows = await postgrest_get(
        "app_users",
        f"select=tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    tenant_id = tenant_rows[0].get("tenant_id") if tenant_rows else None
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User has no tenant assigned")

    return user, tenant_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class CarrierConnectRequest(BaseModel):
    carrier_id: str
    username: str
    password: str
    enterprise_id: Optional[str] = None


class CarrierUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    enterprise_id: Optional[str] = None


class CustomCarrierCreateRequest(BaseModel):
    name: str
    logo: Optional[str] = "🏢"


class CustomCarrierUpdateRequest(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/carriers")
async def list_carriers(authorization: Optional[str] = Header(default=None)):
    """Return all carrier connections for the caller's tenant. Passwords are never included."""
    _, tenant_id = await _require_admin(authorization)

    rows = await postgrest_get(
        "carrier_connections",
        f"select=id,carrier_id,username,enterprise_id,status,connected_at,last_synced_at"
        f"&tenant_id=eq.{quote(tenant_id, safe='')}",
    )
    return {"connections": rows}


@router.post("/api/carriers/connect")
async def connect_carrier(
    body: CarrierConnectRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Connect (or reconnect) a carrier for the caller's tenant. Encrypts password before storage."""
    if not body.carrier_id.strip():
        raise HTTPException(status_code=400, detail="carrier_id is required")
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="username is required")
    if not body.password.strip():
        raise HTTPException(status_code=400, detail="password is required")

    user, tenant_id = await _require_admin(authorization)
    encrypted = _encrypt(body.password)

    existing = await postgrest_get(
        "carrier_connections",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(body.carrier_id, safe='')}",
    )

    payload: dict = {
        "username": body.username.strip(),
        "encrypted_password": encrypted,
        "enterprise_id": (body.enterprise_id or "").strip() or None,
        "status": "active",
    }

    if existing:
        await postgrest_patch(
            "carrier_connections",
            f"id=eq.{quote(existing[0]['id'], safe='')}",
            payload,
        )
    else:
        await postgrest_insert("carrier_connections", {
            **payload,
            "tenant_id": tenant_id,
            "carrier_id": body.carrier_id.strip(),
            "connected_by": user.get("id"),
        })

    return {"message": "Connected successfully"}


@router.patch("/api/carriers/{carrier_id}")
async def update_carrier(
    carrier_id: str,
    body: CarrierUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Update credentials for an existing carrier connection."""
    user, tenant_id = await _require_admin(authorization)

    existing = await postgrest_get(
        "carrier_connections",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(carrier_id, safe='')}",
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Carrier connection not found")

    patch: dict = {}
    if body.username is not None:
        patch["username"] = body.username.strip()
    if body.password is not None and body.password.strip():
        patch["encrypted_password"] = _encrypt(body.password)
    if body.enterprise_id is not None:
        patch["enterprise_id"] = body.enterprise_id.strip() or None

    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    await postgrest_patch(
        "carrier_connections",
        f"id=eq.{quote(existing[0]['id'], safe='')}",
        patch,
    )
    return {"message": "Updated successfully"}


@router.delete("/api/carriers/{carrier_id}")
async def disconnect_carrier(
    carrier_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Remove a carrier connection for the caller's tenant."""
    _, tenant_id = await _require_admin(authorization)

    existing = await postgrest_get(
        "carrier_connections",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(carrier_id, safe='')}",
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Carrier connection not found")

    await postgrest_delete(
        "carrier_connections",
        f"id=eq.{quote(existing[0]['id'], safe='')}",
    )
    return {"message": "Disconnected successfully"}


# ── Custom carrier routes (tenant-specific metadata) ─────────────────────────

def _make_carrier_id(name: str) -> str:
    """Generate a unique slug for a custom carrier from its name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "carrier"
    suffix = secrets.token_hex(3)
    return f"custom-{slug}-{suffix}"


@router.get("/api/carriers/custom")
async def list_custom_carriers(authorization: Optional[str] = Header(default=None)):
    """Return all custom carriers defined for the caller's tenant."""
    _, tenant_id = await _require_admin(authorization)

    rows = await postgrest_get(
        "tenant_carriers",
        f"select=id,carrier_id,name,logo,created_at"
        f"&tenant_id=eq.{quote(tenant_id, safe='')}"
        f"&order=created_at.asc",
    )
    return {"carriers": rows}


@router.post("/api/carriers/custom")
async def add_custom_carrier(
    body: CustomCarrierCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Add a new custom carrier for the caller's tenant."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Carrier name is required")

    user, tenant_id = await _require_admin(authorization)
    carrier_id = _make_carrier_id(body.name)
    logo = (body.logo or "🏢").strip() or "🏢"

    row = await postgrest_insert("tenant_carriers", {
        "tenant_id":  tenant_id,
        "carrier_id": carrier_id,
        "name":       body.name.strip(),
        "logo":       logo,
        "created_by": user.get("id"),
    })

    created = row[0] if row else {}
    return {"message": "Carrier added successfully", "carrier_id": carrier_id, "carrier": created}


@router.patch("/api/carriers/custom/{carrier_id}")
async def update_custom_carrier(
    carrier_id: str,
    body: CustomCarrierUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Update name or logo of an existing custom carrier."""
    _, tenant_id = await _require_admin(authorization)

    existing = await postgrest_get(
        "tenant_carriers",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(carrier_id, safe='')}",
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Custom carrier not found")

    patch: dict = {}
    if body.name is not None and body.name.strip():
        patch["name"] = body.name.strip()
    if body.logo is not None:
        patch["logo"] = body.logo.strip() or "🏢"

    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    await postgrest_patch(
        "tenant_carriers",
        f"id=eq.{quote(existing[0]['id'], safe='')}",
        patch,
    )
    return {"message": "Updated successfully"}


@router.delete("/api/carriers/custom/{carrier_id}")
async def delete_custom_carrier(
    carrier_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Delete a custom carrier and its credentials for the caller's tenant."""
    _, tenant_id = await _require_admin(authorization)

    existing = await postgrest_get(
        "tenant_carriers",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(carrier_id, safe='')}",
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Custom carrier not found")

    # Remove credentials first, then the carrier definition
    await postgrest_delete(
        "carrier_connections",
        f"tenant_id=eq.{quote(tenant_id, safe='')}&carrier_id=eq.{quote(carrier_id, safe='')}",
    )
    await postgrest_delete(
        "tenant_carriers",
        f"id=eq.{quote(existing[0]['id'], safe='')}",
    )
    return {"message": "Carrier removed successfully"}