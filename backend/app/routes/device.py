from datetime import datetime, timezone, timedelta
import json
import hashlib
import secrets
from typing import Any, Optional
from urllib.parse import quote

import httpx
import jwt
import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Request

from app.core.config import DEVICE_JWT_SECRET, DEVICE_OFFLINE_AFTER_SECONDS, LEGACY_DEVICE_TOKEN_APIS_ENABLED, SUPABASE_URL
from app.services.webhook_engine import try_emit_device_online
from app.core.limiter import limiter
from app.core.supabase import (
    get_device_by_token,
    insert_audit_log,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
    verify_admin,
    verify_user,
    get_user_context,
)

log = structlog.get_logger("device")
router = APIRouter()
DEVICE_TOKEN_REQUIRED_DETAIL = "Device token is required"
UTC_OFFSET_SUFFIX = "+00:00"


def _require_legacy_device_apis_enabled() -> None:
    """Gate legacy /api/device-* endpoints behind an explicit env toggle."""
    if LEGACY_DEVICE_TOKEN_APIS_ENABLED:
        return
    raise HTTPException(
        status_code=410,
        detail=(
            "Legacy token-based device APIs are disabled. "
            "Use /api/v1/devices/register and /api/v1/devices/heartbeat."
        ),
    )


def _extract_magic_link_payload(body: dict, user_email: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    sources = [body, body.get("properties") if isinstance(body, dict) else None]
    for source in sources:
        if not isinstance(source, dict):
            continue
        action_link = source.get("action_link")
        email_otp = source.get("email_otp")
        if isinstance(action_link, str) and action_link:
            return action_link, None, None, None
        if isinstance(email_otp, str) and email_otp:
            return None, user_email, email_otp, None
    return None, None, None, "No action_link or email_otp returned from Supabase generate_link API"


def _parse_utc_iso(raw: Any) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", UTC_OFFSET_SUFFIX))

def _normalize_device_status_row(row: dict[str, Any], *, now: datetime) -> None:
    """
    Ensure the returned device status reflects reality even if background sweeps
    are disabled/delayed in a given environment.
    """
    try:
        status = str(row.get("status") or "").strip().lower()
        last_seen_raw = row.get("last_seen_at")
        if not last_seen_raw:
            # Unseen devices are explicitly "never_checked_in" for UI clarity.
            if status == "online":
                row["status"] = "never_checked_in"
            return

        last_seen = _parse_utc_iso(last_seen_raw)
        cutoff = now - timedelta(seconds=float(DEVICE_OFFLINE_AFTER_SECONDS))
        if status == "online" and last_seen < cutoff:
            row["status"] = "offline"
    except Exception:
        # Best-effort only; never block admin APIs.
        return


async def _generate_magic_login_link(
    user_email: str, redirect_to: str
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    payload = {
        "type": "magiclink",
        "email": user_email,
        "options": {"redirect_to": redirect_to},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/generate_link",
            headers=service_headers(),
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        return None, None, None, resp.text
    body = resp.json()
    return _extract_magic_link_payload(body, user_email)


async def _resolve_device_from_bearer(authorization: Optional[str]) -> tuple[str, dict[str, Any]]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Device JWT required")
    claims = _verify_device_jwt(authorization.split(" ", 1)[1])
    device_id = claims.get("device_id")
    if not device_id:
        raise HTTPException(status_code=401, detail="Invalid device JWT claims")
    return str(device_id), claims


async def _load_active_device_row(device_id: str) -> dict[str, Any]:
    rows = await postgrest_get(
        "devices",
        f"select=id,is_active,jwt_issued_after,hardware_fingerprint_hash&id=eq.{quote(device_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Device not found")
    device_row = rows[0]
    if not device_row.get("is_active", False):
        raise HTTPException(status_code=403, detail="Device is deactivated")
    return device_row


def _enforce_not_revoked(claims: dict[str, Any], jwt_issued_after_raw: Any) -> None:
    if not jwt_issued_after_raw:
        return
    try:
        issued_after_ts = _parse_utc_iso(jwt_issued_after_raw).timestamp()
    except ValueError:
        issued_after_ts = 0
    if claims.get("iat", 0) < issued_after_ts:
        raise HTTPException(status_code=401, detail="Device token has been revoked — please re-register")


def _enforce_fingerprint_matches_device(claims: dict[str, Any], device_row: dict[str, Any]) -> None:
    """Reject JWTs that do not match the hardware fingerprint stored for this device (stolen-token reuse)."""
    db_fp = device_row.get("hardware_fingerprint_hash")
    if not db_fp:
        return
    claim_fp = claims.get("hardware_fingerprint_hash")
    if not claim_fp or str(claim_fp) != str(db_fp):
        raise HTTPException(
            status_code=401,
            detail="Device identity mismatch — re-register with this machine's hardware fingerprint",
        )


async def _sync_local_models(device_id: str, local_models: Any, now: datetime) -> None:
    if not isinstance(local_models, list):
        return
    for local_model in local_models:
        if not isinstance(local_model, dict):
            continue
        model_id = str(local_model.get("model_id") or "").strip()
        is_downloaded = bool(local_model.get("is_downloaded"))
        if not model_id:
            continue
        await postgrest_patch(
            "device_models",
            f"device_id=eq.{quote(device_id, safe='')}&model_id=eq.{quote(model_id, safe='')}",
            {"is_downloaded": is_downloaded, "last_synced_at": now.isoformat()},
        )


async def _get_pending_pairing_or_fail(pairing_id: str) -> dict[str, Any]:
    rows = await postgrest_get(
        "device_pairings",
        f"select=*&id=eq.{quote(pairing_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pairing session not found")
    pairing = rows[0]
    now = datetime.now(timezone.utc)
    expires_at = _parse_utc_iso(pairing["expires_at"])
    if pairing.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Pairing session is not pending")
    if expires_at < now:
        await postgrest_patch(
            "device_pairings",
            f"id=eq.{quote(pairing_id, safe='')}",
            {"status": "expired"},
        )
        raise HTTPException(status_code=400, detail="Pairing session expired")
    return pairing


def _validate_pairing_code(pairing_code: str, expected_hash: Any) -> None:
    received_hash = hashlib.sha256(pairing_code.encode("utf-8")).hexdigest()
    if not expected_hash or received_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Invalid pairing code")


def _parse_registration_payload(body: dict[str, Any]) -> tuple[str, str, Any, Any, dict[str, Any], datetime, Optional[str]]:
    raw_fingerprint = str(body.get("hardware_fingerprint") or "").strip()
    legacy_device_token = str(body.get("device_token") or "").strip() or None

    if raw_fingerprint:
        fingerprint_hash = hashlib.sha256(raw_fingerprint.lower().encode("utf-8")).hexdigest()
        registered_via = "hardware_fingerprint"
    elif legacy_device_token:
        # Allow migrating legacy device_token-based enrollment to v1 without requiring
        # a hardware fingerprint implementation immediately.
        fingerprint_hash = hashlib.sha256(f"legacy:{legacy_device_token}".encode("utf-8")).hexdigest()
        registered_via = "legacy_device_token"
    else:
        raise HTTPException(status_code=400, detail="hardware_fingerprint or device_token is required")

    device_name = str(body.get("device_name") or "").strip() or "Unknown Device"
    os_type = body.get("os_type")
    app_version = body.get("app_version")
    extra_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    extra_metadata.setdefault("registered_via", registered_via)
    return fingerprint_hash, device_name, os_type, app_version, extra_metadata, datetime.now(timezone.utc), legacy_device_token


async def _upsert_device_for_registration(
    fingerprint_hash: str,
    device_name: str,
    os_type: Any,
    app_version: Any,
    extra_metadata: dict[str, Any],
    now: datetime,
    legacy_device_token: Optional[str] = None,
) -> tuple[dict[str, Any], bool]:
    if legacy_device_token:
        device = await get_device_by_token(legacy_device_token)
        await postgrest_patch(
            "devices",
            f"id=eq.{quote(device['id'], safe='')}",
            {
                "device_name": device_name or device.get("device_name"),
                "os_type": os_type or device.get("os_type"),
                "app_version": app_version or device.get("app_version"),
                "hardware_fingerprint_hash": fingerprint_hash,
                "status": "online",
                "last_seen_at": now.isoformat(),
                "jwt_issued_after": now.isoformat(),
                "metadata": {**(device.get("metadata") or {}), **extra_metadata},
            },
        )
        device["device_name"] = device_name or device.get("device_name")
        device["hardware_fingerprint_hash"] = fingerprint_hash
        return device, False

    existing = await postgrest_get(
        "devices",
        f"select=*&hardware_fingerprint_hash=eq.{quote(fingerprint_hash, safe='')}&limit=1",
    )
    if existing:
        device = existing[0]
        await postgrest_patch(
            "devices",
            f"id=eq.{quote(device['id'], safe='')}",
            {
                "device_name": device_name or device.get("device_name"),
                "os_type": os_type or device.get("os_type"),
                "app_version": app_version or device.get("app_version"),
                "status": "online",
                "last_seen_at": now.isoformat(),
                "jwt_issued_after": now.isoformat(),
            },
        )
        device["device_name"] = device_name or device.get("device_name")
        return device, False

    inserted = await postgrest_insert(
        "devices",
        {
            "device_name": device_name,
            "device_token": secrets.token_urlsafe(32),
            "hardware_fingerprint_hash": fingerprint_hash,
            # Ensure new devices are immediately usable; some DBs default is_active to false/null.
            "is_active": True,
            "status": "online",
            "os_type": os_type,
            "app_version": app_version,
            "last_seen_at": now.isoformat(),
            "jwt_issued_after": now.isoformat(),
            "metadata": {
                **extra_metadata,
            },
        },
    )
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to create device")
    return inserted[0], True


@router.get("/api/device-models")
async def device_models(x_device_token: Optional[str] = Header(default=None)):
    _require_legacy_device_apis_enabled()
    if not x_device_token:
        raise HTTPException(status_code=400, detail=DEVICE_TOKEN_REQUIRED_DETAIL)
    device = await get_device_by_token(x_device_token)
    models = await postgrest_get(
        "device_models",
        f"select=*&device_id=eq.{quote(device['id'], safe='')}&order=allocated_at.desc",
    )
    mapped = [
        {
            "model_id": m.get("model_id"),
            "model_name": m.get("model_name"),
            "domain": m.get("domain"),
            "ollama_model_name": m.get("ollama_model_name") or "llama3.2:latest",
            "is_downloaded": m.get("is_downloaded"),
            "allocated_at": m.get("allocated_at"),
        }
        for m in models
    ]
    return {"success": True, "device_id": device["id"], "models": mapped, "total_models": len(mapped)}


@router.post("/api/device-checkin")
async def device_checkin(request: Request, x_device_token: Optional[str] = Header(default=None)):
    _require_legacy_device_apis_enabled()
    if not x_device_token:
        raise HTTPException(status_code=400, detail=DEVICE_TOKEN_REQUIRED_DETAIL)
    device = await get_device_by_token(x_device_token)
    body = await request.json()
    os_type = body.get("os_type")
    app_version = body.get("app_version")
    local_models = body.get("local_models", [])

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device['id'], safe='')}",
        {
            "status": "online",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "os_type": os_type or device.get("os_type"),
            "app_version": app_version or device.get("app_version"),
        },
    )

    if isinstance(local_models, list):
        for local_model in local_models:
            model_id = local_model.get("model_id") if isinstance(local_model, dict) else local_model
            if model_id:
                await postgrest_patch(
                    "device_models",
                    f"device_id=eq.{quote(device['id'], safe='')}&model_id=eq.{quote(str(model_id), safe='')}",
                    {"is_downloaded": True, "last_synced_at": datetime.now(timezone.utc).isoformat()},
                )

    return {"success": True, "device_id": device["id"], "status": "online", "message": "Check-in successful"}


@router.post("/api/device-register")
async def device_register(request: Request):
    _require_legacy_device_apis_enabled()
    body = await request.json()
    device_token = body.get("device_token")
    if not device_token:
        raise HTTPException(status_code=400, detail=DEVICE_TOKEN_REQUIRED_DETAIL)
    device = await get_device_by_token(device_token)
    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device['id'], safe='')}",
        {
            "device_name": body.get("device_name") or device.get("device_name"),
            "os_type": body.get("os_type") or device.get("os_type"),
            "app_version": body.get("app_version") or device.get("app_version"),
            "status": "online",
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {
        "success": True,
        "device_id": device["id"],
        "device_name": device.get("device_name"),
        "message": "Device registered successfully",
    }


def _verify_device_jwt(token: str) -> dict:
    """Decode and verify a device JWT signed by DEVICE_JWT_SECRET. Raises 401 on failure."""
    try:
        return jwt.decode(token, DEVICE_JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Device token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid device token")


def _sign_device_jwt(device_id: str, device_name: str, hardware_fingerprint_hash: str) -> str:
    """Sign a HS256 JWT that identifies a registered device."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": device_id,
        "device_id": device_id,
        "device_name": device_name,
        "hardware_fingerprint_hash": hardware_fingerprint_hash,
        "type": "device",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=365)).timestamp()),
    }
    return jwt.encode(payload, DEVICE_JWT_SECRET, algorithm="HS256")


@router.post("/api/v1/devices/register")
@limiter.limit("10/minute")
async def register_device_v1(request: Request):  # noqa: C901
    """
    Register a device by hardware fingerprint and return a signed JWT device token.
    Idempotent: re-registering the same hardware fingerprint returns a new JWT for
    the same device record (no duplicate device is created).

    Body:
        hardware_fingerprint (str, required): Raw hardware identifier from the device.
        device_name (str, optional): Human-readable device label.
        os_type (str, optional): Operating system type (e.g. "linux", "windows").
        app_version (str, optional): Running app version string.
        metadata (dict, optional): Additional key/value pairs stored in device metadata.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}")
    fingerprint_hash, device_name, os_type, app_version, extra_metadata, now, legacy_device_token = _parse_registration_payload(body)
    device, is_new = await _upsert_device_for_registration(
        fingerprint_hash=fingerprint_hash,
        device_name=device_name,
        os_type=os_type,
        app_version=app_version,
        extra_metadata=extra_metadata,
        now=now,
        legacy_device_token=legacy_device_token,
    )

    signed_token = _sign_device_jwt(
        device_id=device["id"],
        device_name=device["device_name"],
        hardware_fingerprint_hash=fingerprint_hash,
    )

    await insert_audit_log(
        request=request,
        user_id=None,
        action="device_registered" if is_new else "device_re_registered",
        resource_type="device",
        resource_id=device["id"],
        details={"device_name": device["device_name"], "os_type": os_type, "is_new": is_new},
        previous_value=None,
        new_value={"status": "online"},
    )
    log.info("device.registered", device_id=device["id"], is_new=is_new)
    await try_emit_device_online(str(device["id"]), force=True)

    return {
        "success": True,
        "device_token": signed_token,
        "device_id": device["id"],
        "device_name": device["device_name"],
        "is_new": is_new,
    }


@router.get("/api/v1/devices/models")
async def device_models_v1(authorization: Optional[str] = Header(default=None)):
    """Return allocated models for a device using Bearer device JWT."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Device JWT required")
    claims = _verify_device_jwt(authorization.split(" ", 1)[1])
    device_id = claims.get("device_id")
    if not device_id:
        raise HTTPException(status_code=401, detail="Invalid device JWT claims")

    device_row = await _load_active_device_row(str(device_id))
    _enforce_not_revoked(claims, device_row.get("jwt_issued_after"))
    _enforce_fingerprint_matches_device(claims, device_row)

    models = await postgrest_get(
        "device_models",
        f"select=*&device_id=eq.{quote(device_id, safe='')}&order=allocated_at.desc",
    )
    mapped = [
        {
            "model_id": m.get("model_id"),
            "model_name": m.get("model_name"),
            "domain": m.get("domain"),
            "ollama_model_name": m.get("ollama_model_name") or "llama3.2:latest",
            "is_downloaded": m.get("is_downloaded"),
            "allocated_at": m.get("allocated_at"),
        }
        for m in models
    ]
    return {"success": True, "device_id": device_id, "models": mapped, "total_models": len(mapped)}


@router.put("/api/v1/devices/heartbeat")
@limiter.limit("60/minute")
async def device_heartbeat(request: Request, authorization: Optional[str] = Header(default=None)):
    """
    Heartbeat endpoint. Devices call this every 60 s to stay marked online.
    Auth: Authorization: Bearer <device_jwt>  (JWT issued by /api/v1/devices/register)
    A device that misses 3 consecutive beats (180 s) is marked offline by the
    background offline-detector task.

    Rate limit: 60/minute per IP (devices normally send ~1/minute but the Electron
    shell can burst/retry during startup or when multiple renderers race).
    """
    device_id, claims = await _resolve_device_from_bearer(authorization)
    device_row = await _load_active_device_row(device_id)
    _enforce_not_revoked(claims, device_row.get("jwt_issued_after"))
    _enforce_fingerprint_matches_device(claims, device_row)

    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    local_models = body.get("local_models", [])
    now = datetime.now(timezone.utc)

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {"status": "online", "last_seen_at": now.isoformat()},
    )

    await _sync_local_models(device_id, local_models, now)
    log.debug("device.heartbeat", device_id=device_id)
    await try_emit_device_online(device_id, force=False)

    # Return pending model IDs so the device can start pulling without waiting for a realtime push.
    pending_rows = await postgrest_get(
        "device_models",
        f"select=model_id,model_name,ollama_model_name&device_id=eq.{quote(device_id, safe='')}&is_downloaded=eq.false&limit=50",
    )
    pending_downloads = [
        {
            "model_id": r.get("model_id"),
            "model_name": r.get("model_name"),
            "ollama_model_name": r.get("ollama_model_name") or "llama3.2:latest",
        }
        for r in (pending_rows or [])
        if r.get("model_id")
    ]

    return {
        "success": True,
        "device_id": device_id,
        "last_seen_at": now.isoformat(),
        "pending_downloads": pending_downloads,
        "pending_count": len(pending_downloads),
    }


@router.post("/api/v1/devices/offline")
async def device_offline(authorization: Optional[str] = Header(default=None)):
    """
    Explicitly mark the device as offline (e.g., during user logout).
    """
    device_id, claims = await _resolve_device_from_bearer(authorization)
    device_row = await _load_active_device_row(device_id)
    _enforce_not_revoked(claims, device_row.get("jwt_issued_after"))
    _enforce_fingerprint_matches_device(claims, device_row)

    now = datetime.now(timezone.utc)
    # To force it offline instantly in the UI, we push last_seen_at back in time
    # beyond the 3-minute cutoff.
    past_time = now - timedelta(minutes=5)

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {"status": "offline", "last_seen_at": past_time.isoformat()},
    )
    log.info("device.offline_explicit", device_id=device_id)
    return {"success": True, "device_id": device_id, "status": "offline"}


@router.post("/api/v1/devices/{device_id}/revoke")
async def revoke_device(
    device_id: str = Path(...),
    authorization: Optional[str] = Header(default=None),
):
    """
    Admin endpoint: immediately revoke all JWTs for a device and deactivate it.

    Sets jwt_issued_after = NOW() and is_active = false on the device row.
    Any existing device JWT issued before this moment will be rejected by the
    heartbeat endpoint, forcing the device to re-register (which requires a
    new hardware fingerprint scan).

    Auth: Supabase user JWT with admin role.
    """
    await verify_admin(authorization)  # raises 401/403 if not a valid admin user
    requester_context = await get_user_context(authorization)
    requester_role = requester_context.get("role")
    requester_tenant_id = requester_context.get("tenant_id")

    now = datetime.now(timezone.utc)
    rows = await postgrest_get(
        "devices",
        f"select=id,tenant_id,registered_by&id=eq.{quote(device_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Device not found")
    target = rows[0]

    if requester_role in {"admin", "global_admin"}:
        if not requester_tenant_id:
            raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
        target_tenant_id = target.get("tenant_id")
        # Backward compatibility: derive tenant via registered_by for legacy rows.
        if not target_tenant_id and target.get("registered_by"):
            owner_rows = await postgrest_get(
                "app_users",
                f"select=tenant_id&user_id=eq.{quote(str(target['registered_by']), safe='')}&limit=1",
            )
            target_tenant_id = owner_rows[0].get("tenant_id") if owner_rows else None
        if target_tenant_id != requester_tenant_id:
            raise HTTPException(status_code=403, detail="Cross-tenant device access denied")

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        {
            "is_active": False,
            "status": "offline",
            "jwt_issued_after": now.isoformat(),
        },
    )
    log.info("device.revoked", device_id=device_id)
    return {"success": True, "device_id": device_id, "revoked_at": now.isoformat()}


@router.post("/api/v1/devices/link")
async def link_device_v1(request: Request, authorization: Optional[str] = Header(default=None)):
    """
    Link an already-registered device to the current (authenticated) user + tenant.

    This is the "manual device id" pairing flow:
    - Electron shows the device_id to the user
    - User pastes it in the Cloud UI
    - Backend associates the device with their tenant/user
    """
    user = await verify_user(authorization)
    requester_context = await get_user_context(authorization)
    requester_role = requester_context.get("role")
    requester_tenant_id = requester_context.get("tenant_id")
    # Tenant scoping is required for linking devices (including global_admin) so
    # devices are always assigned to an explicit tenant.
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    rows = await postgrest_get(
        "devices",
        f"select=id,tenant_id,registered_by,metadata&id=eq.{quote(device_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Device not found")
    target = rows[0]

    target_tenant_id = target.get("tenant_id")
    if target_tenant_id and str(target_tenant_id) != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant device access denied")

    now = datetime.now(timezone.utc)
    existing_meta = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
    new_meta = {
        **existing_meta,
        "linked_via": "manual_device_id",
        "linked_at": now.isoformat(),
        "linked_by": user["id"],
    }

    patch: dict[str, Any] = {
        "registered_by": user["id"],
        "metadata": new_meta,
    }
    patch["tenant_id"] = requester_tenant_id

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device_id, safe='')}",
        patch,
    )

    await insert_audit_log(
        request=request,
        user_id=user["id"],
        action="device_linked",
        resource_type="device",
        resource_id=device_id,
        details={"linked_via": "manual_device_id"},
        previous_value=None,
        new_value={"tenant_id": requester_tenant_id, "registered_by": user["id"]},
    )
    log.info("device.linked", device_id=device_id, user_id=user["id"], tenant_id=requester_tenant_id)
    return {"success": True, "device_id": device_id}


@router.get("/api/v1/admin/devices")
async def list_devices_admin(authorization: Optional[str] = Header(default=None)):
    """
    Admin list of devices.

    Uses service-role PostgREST calls (bypasses RLS), gated by admin auth.
    """
    await verify_admin(authorization)
    requester_context = await get_user_context(authorization)
    requester_role = requester_context.get("role")
    requester_tenant_id = requester_context.get("tenant_id")

    # Tenant scoping: even global_admin is scoped to their tenant for this API.
    filters = []
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
    filters.append(f"tenant_id=eq.{quote(str(requester_tenant_id), safe='')}")

    where = "&".join(filters)
    if where:
        where = "&" + where

    rows = await postgrest_get(
        "devices",
        (
            "select=id,device_name,status,last_seen_at,os_type,app_version,registered_by,tenant_id,created_at"
            f"{where}"
            "&order=last_seen_at.desc.nullslast"
            "&limit=200"
        ),
    )
    now = datetime.now(timezone.utc)
    for r in rows or []:
        if isinstance(r, dict):
            _normalize_device_status_row(r, now=now)
    user_ids = sorted({str(r.get("registered_by")) for r in (rows or []) if r.get("registered_by")})
    if user_ids:
        encoded_ids = ",".join(quote(uid, safe="") for uid in user_ids)
        users = await postgrest_get(
            "app_users",
            f"select=user_id,email,full_name&user_id=in.({encoded_ids})&limit=2000",
        )
        user_map = {str(u.get("user_id")): u for u in (users or []) if u.get("user_id")}
        for r in rows or []:
            uid = r.get("registered_by")
            if not uid:
                continue
            u = user_map.get(str(uid))
            if not u:
                continue
            r["registered_by_email"] = u.get("email")
            r["registered_by_name"] = u.get("full_name")
    return {"success": True, "devices": rows}


@router.get("/api/v1/admin/devices/{device_id}")
async def get_device_admin(device_id: str = Path(...), authorization: Optional[str] = Header(default=None)):
    """
    Admin device details view.
    Uses service-role PostgREST calls (bypasses RLS), gated by admin auth.
    """
    await verify_admin(authorization)
    requester_context = await get_user_context(authorization)
    requester_role = requester_context.get("role")
    requester_tenant_id = requester_context.get("tenant_id")

    device_rows = await postgrest_get(
        "devices",
        f"select=*&id=eq.{quote(device_id, safe='')}&limit=1",
    )
    if not device_rows:
        raise HTTPException(status_code=404, detail="Device not found")
    device = device_rows[0]
    if isinstance(device, dict):
        _normalize_device_status_row(device, now=datetime.now(timezone.utc))

    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
    if str(device.get("tenant_id") or "") != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant device access denied")

    # Enrich with linked user label fields (for breadcrumb / details header).
    try:
        registered_by = device.get("registered_by")
        if registered_by:
            users = await postgrest_get(
                "app_users",
                f"select=user_id,email,full_name&user_id=eq.{quote(str(registered_by), safe='')}&limit=1",
            )
            if users:
                u = users[0] or {}
                device["registered_by_email"] = u.get("email")
                device["registered_by_name"] = u.get("full_name")
    except Exception:
        # Best-effort enrichment; don't block admin reads.
        pass

    models = await postgrest_get(
        "device_models",
        f"select=*&device_id=eq.{quote(device_id, safe='')}&order=allocated_at.desc&limit=500",
    )
    sync_logs = await postgrest_get(
        "device_sync_logs",
        f"select=*&device_id=eq.{quote(device_id, safe='')}&order=created_at.desc&limit=50",
    )
    usage_logs = await postgrest_get(
        "device_usage_logs",
        f"select=*&device_id=eq.{quote(device_id, safe='')}&order=logged_at.desc&limit=50",
    )
    available_models = await postgrest_get(
        "activated_models",
        "select=id,model_id,model_name,domain&limit=200",
    )

    return {
        "success": True,
        "device": device,
        "device_models": models,
        "sync_logs": sync_logs,
        "usage_logs": usage_logs,
        "available_models": available_models,
    }


@router.post("/api/devices/pairing/start")
async def start_device_pairing(request: Request, authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    body = await request.json()

    expires_in_seconds = int(body.get("expires_in_seconds") or 120)
    if expires_in_seconds < 30 or expires_in_seconds > 600:
        raise HTTPException(status_code=400, detail="expires_in_seconds must be between 30 and 600")

    pairing_code = secrets.token_urlsafe(18)
    pairing_code_hash = hashlib.sha256(pairing_code.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(now.timestamp() + expires_in_seconds, tz=timezone.utc)

    requested_profile = body.get("requested_device_profile")
    if not isinstance(requested_profile, dict):
        requested_profile = {}

    primary_device_label = body.get("primary_device_label")
    if primary_device_label and not isinstance(primary_device_label, str):
        primary_device_label = None

    inserted_rows = await postgrest_insert(
        "device_pairings",
        {
            "user_id": user["id"],
            "pairing_code_hash": pairing_code_hash,
            "status": "pending",
            "expires_at": expires_at.isoformat(),
            "requested_device_profile": requested_profile,
            "primary_device_label": primary_device_label,
        },
    )
    if not inserted_rows:
        raise HTTPException(status_code=500, detail="Failed to create device pairing")

    pairing = inserted_rows[0]
    pairing_id = pairing["id"]
    frontend_base = str(body.get("frontend_base_url") or "").strip().rstrip("/")
    if not frontend_base:
        origin = request.headers.get("origin")
        if origin:
            frontend_base = origin.rstrip("/")
    if not frontend_base:
        frontend_base = "http://localhost:3000"

    # Use root URL + query so QR opens reliably on deployments
    # where deep links like /device-link return 404 from the web server.
    pairing_url = f"{frontend_base}/?pair=1&pid={quote(pairing_id, safe='')}&code={quote(pairing_code, safe='')}"

    return {
        "success": True,
        "pairing_id": pairing_id,
        "pairing_code": pairing_code,
        "pairing_url": pairing_url,
        "expires_at": pairing["expires_at"],
        "status": pairing["status"],
    }


@router.get("/api/devices/pairing/status/{pairing_id}")
async def get_device_pairing_status(
    pairing_id: str = Path(..., min_length=1),
    authorization: Optional[str] = Header(default=None),
):
    user = await verify_user(authorization)
    rows = await postgrest_get(
        "device_pairings",
        (
            "select=id,user_id,status,expires_at,consumed_at,linked_device_id,created_at,confirmed_device_profile"
            f"&id=eq.{quote(pairing_id, safe='')}&user_id=eq.{quote(user['id'], safe='')}&limit=1"
        ),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pairing not found")

    pairing = rows[0]
    now = datetime.now(timezone.utc)
    expires_at = _parse_utc_iso(pairing["expires_at"])
    if pairing["status"] == "pending" and expires_at < now:
        await postgrest_patch(
            "device_pairings",
            f"id=eq.{quote(pairing_id, safe='')}",
            {"status": "expired"},
        )
        pairing["status"] = "expired"

    return {"success": True, "pairing": pairing}


@router.post("/api/devices/pairing/confirm")
async def confirm_device_pairing(request: Request):
    body = await request.json()
    pairing_id = str(body.get("pairing_id") or "").strip()
    pairing_code = str(body.get("pairing_code") or "").strip()
    if not pairing_id or not pairing_code:
        raise HTTPException(status_code=400, detail="pairing_id and pairing_code are required")

    pairing = await _get_pending_pairing_or_fail(pairing_id)
    now = datetime.now(timezone.utc)
    _validate_pairing_code(pairing_code, pairing.get("pairing_code_hash"))

    confirmed_profile = body.get("confirmed_device_profile")
    if not isinstance(confirmed_profile, dict):
        confirmed_profile = {}

    device_name = str(body.get("device_name") or confirmed_profile.get("device_name") or "Linked Device").strip()
    if not device_name:
        device_name = "Linked Device"
    os_type = body.get("os_type") or confirmed_profile.get("os_name")
    app_version = body.get("app_version") or confirmed_profile.get("app_version")

    device_token = secrets.token_urlsafe(32)
    inserted_devices = await postgrest_insert(
        "devices",
        {
            "device_name": device_name,
            "device_token": device_token,
            "registered_by": pairing["user_id"],
            "status": "online",
            "os_type": os_type,
            "app_version": app_version,
            "last_seen_at": now.isoformat(),
            "jwt_issued_after": now.isoformat(),
            "metadata": {
                "linked_from_pairing": True,
                "pairing_id": pairing_id,
                "requested_device_profile": pairing.get("requested_device_profile") or {},
                "confirmed_device_profile": confirmed_profile,
            },
        },
    )
    if not inserted_devices:
        raise HTTPException(status_code=500, detail="Failed to create linked device")
    linked_device = inserted_devices[0]

    await postgrest_patch(
        "device_pairings",
        f"id=eq.{quote(pairing_id, safe='')}",
        {
            "status": "confirmed",
            "consumed_at": now.isoformat(),
            "linked_device_id": linked_device["id"],
            "confirmed_device_profile": confirmed_profile,
        },
    )
    await insert_audit_log(
        request=request,
        user_id=pairing["user_id"],
        action="device_pairing_confirmed",
        resource_type="device",
        resource_id=linked_device["id"],
        details={"pairing_id": pairing_id, "device_name": device_name},
        previous_value=None,
        new_value={"status": "confirmed"},
    )

    user_rows = await postgrest_get(
        "app_users",
        f"select=email&user_id=eq.{quote(pairing['user_id'], safe='')}&limit=1",
    )
    user_email = user_rows[0].get("email") if user_rows else None
    redirect_to = str(body.get("auth_redirect_to") or "").strip()
    if not redirect_to:
        origin = request.headers.get("origin")
        redirect_to = f"{origin.rstrip('/')}/auth" if origin else ""
    login_action_link = None
    login_email = None
    login_email_otp = None
    login_handoff_error = None
    if user_email and redirect_to:
        login_action_link, login_email, login_email_otp, login_handoff_error = await _generate_magic_login_link(
            user_email, redirect_to
        )
    elif not user_email:
        login_handoff_error = "User email not found"
    else:
        login_handoff_error = "auth_redirect_to is required for login handoff"

    return {
        "success": True,
        "pairing_id": pairing_id,
        "device": {
            "id": linked_device["id"],
            "name": linked_device["device_name"],
            "token": linked_device["device_token"],
        },
        "login_action_link": login_action_link,
        "login_email": login_email,
        "login_email_otp": login_email_otp,
        "login_handoff_error": login_handoff_error,
        "status": "confirmed",
    }
