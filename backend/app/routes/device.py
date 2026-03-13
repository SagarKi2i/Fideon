from datetime import datetime, timezone
import json
import hashlib
import secrets
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Path, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import get_device_by_token, postgrest_get, postgrest_insert, postgrest_patch, verify_user
from app.core.supabase import service_headers

router = APIRouter()


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
    if isinstance(body, dict):
        action_link_top = body.get("action_link")
        email_otp_top = body.get("email_otp")
        if isinstance(action_link_top, str) and action_link_top:
            return action_link_top, None, None, None
        if isinstance(email_otp_top, str) and email_otp_top:
            return None, user_email, email_otp_top, None
    properties = body.get("properties") if isinstance(body, dict) else None
    if isinstance(properties, dict):
        action_link = properties.get("action_link")
        email_otp = properties.get("email_otp")
        if isinstance(action_link, str) and action_link:
            return action_link, None, None, None
        if isinstance(email_otp, str) and email_otp:
            return None, user_email, email_otp, None
    return None, None, None, "No action_link or email_otp returned from Supabase generate_link API"


@router.get("/api/device-models")
async def device_models(x_device_token: Optional[str] = Header(default=None)):
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
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
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
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
            "last_seen_at": datetime.utcnow().isoformat(),
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
                    {"is_downloaded": True, "last_synced_at": datetime.utcnow().isoformat()},
                )

    return {"success": True, "device_id": device["id"], "status": "online", "message": "Check-in successful"}


@router.post("/api/device-register")
async def device_register(request: Request):
    body = await request.json()
    device_token = body.get("device_token")
    if not device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
    device = await get_device_by_token(device_token)
    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device['id'], safe='')}",
        {
            "device_name": body.get("device_name") or device.get("device_name"),
            "os_type": body.get("os_type") or device.get("os_type"),
            "app_version": body.get("app_version") or device.get("app_version"),
            "status": "online",
            "last_seen_at": datetime.utcnow().isoformat(),
        },
    )
    return {
        "success": True,
        "device_id": device["id"],
        "device_name": device.get("device_name"),
        "message": "Device registered successfully",
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
    expires_at = datetime.fromisoformat(str(pairing["expires_at"]).replace("Z", "+00:00"))
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

    rows = await postgrest_get(
        "device_pairings",
        f"select=*&id=eq.{quote(pairing_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pairing session not found")

    pairing = rows[0]
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(str(pairing["expires_at"]).replace("Z", "+00:00"))
    if pairing.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Pairing session is not pending")
    if expires_at < now:
        await postgrest_patch(
            "device_pairings",
            f"id=eq.{quote(pairing_id, safe='')}",
            {"status": "expired"},
        )
        raise HTTPException(status_code=400, detail="Pairing session expired")

    expected_hash = pairing.get("pairing_code_hash")
    received_hash = hashlib.sha256(pairing_code.encode("utf-8")).hexdigest()
    if not expected_hash or received_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Invalid pairing code")

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
