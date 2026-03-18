import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import PERSONAL_API_KEY_PEPPER
from app.core.supabase import (
    insert_audit_log,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    verify_user,
)

router = APIRouter()


def _normalize_preferences(metadata: dict) -> dict:
    settings = metadata.get("settings_preferences") if isinstance(metadata, dict) else {}
    if not isinstance(settings, dict):
        settings = {}
    return {
        "email_notifications": bool(settings.get("email_notifications", True)),
        "product_updates": bool(settings.get("product_updates", True)),
    }


async def _get_user_role(user_id: str) -> Optional[str]:
    role_rows = await postgrest_get(
        "user_roles",
        f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    return role_rows[0].get("role") if role_rows else None


def _hash_api_key(raw_key: str) -> str:
    payload = f"{PERSONAL_API_KEY_PEPPER}{raw_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@router.get("/api/settings/profile")
async def get_profile(authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows = await postgrest_get(
        "app_users",
        f"select=user_id,email,full_name,metadata&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User profile not found")

    profile = rows[0]
    metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    preferences = _normalize_preferences(metadata)
    role = await _get_user_role(user_id)
    return {
        "profile": {
            "user_id": profile.get("user_id"),
            "email": profile.get("email"),
            "full_name": profile.get("full_name") or "",
            "role": role or "user",
            "preferences": preferences,
        }
    }


@router.patch("/api/settings/profile")
async def update_profile(request: Request, authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    full_name = str(body.get("full_name") or "").strip()
    if len(full_name) > 120:
        raise HTTPException(status_code=400, detail="full_name must be 120 characters or fewer")

    incoming_preferences = body.get("preferences")
    if incoming_preferences is None or not isinstance(incoming_preferences, dict):
        raise HTTPException(status_code=400, detail="preferences must be an object")

    rows = await postgrest_get(
        "app_users",
        f"select=full_name,metadata&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User profile not found")

    before = rows[0]
    metadata = before.get("metadata") if isinstance(before.get("metadata"), dict) else {}
    normalized_preferences = {
        "email_notifications": bool(incoming_preferences.get("email_notifications", True)),
        "product_updates": bool(incoming_preferences.get("product_updates", True)),
    }
    new_metadata = {
        **metadata,
        "settings_preferences": normalized_preferences,
    }

    await postgrest_patch(
        "app_users",
        f"user_id=eq.{quote(user_id, safe='')}",
        {
            "full_name": full_name or None,
            "metadata": new_metadata,
        },
    )

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action="update_profile_settings",
        resource_type="app_user",
        resource_id=user_id,
        details={"preferences_updated": True},
        previous_value={
            "full_name": before.get("full_name"),
            "settings_preferences": _normalize_preferences(metadata),
        },
        new_value={
            "full_name": full_name or None,
            "settings_preferences": normalized_preferences,
        },
    )

    return {"success": True}


@router.get("/api/settings/api-keys")
async def list_personal_api_keys(authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows = await postgrest_get(
        "personal_api_keys",
        (
            "select=id,name,key_prefix,key_prefix_sha256,created_at,last_used_at,revoked_at"
            f"&user_id=eq.{quote(user_id, safe='')}"
            "&order=created_at.desc"
        ),
    )
    return {"keys": rows}


@router.post("/api/settings/api-keys")
async def create_personal_api_key(request: Request, authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="name must be 80 characters or fewer")

    raw_key = f"nbk_{secrets.token_urlsafe(32)}"
    key_hash_sha256 = _hash_api_key(raw_key)
    key_prefix = raw_key[:12]
    key_prefix_sha256 = key_hash_sha256[:12]

    inserted = await postgrest_insert(
        "personal_api_keys",
        {
            "user_id": user_id,
            "name": name,
            "key_prefix": key_prefix,
            "key_hash_sha256": key_hash_sha256,
            "key_prefix_sha256": key_prefix_sha256,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    created = inserted[0] if inserted else None
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action="create_personal_api_key",
        resource_type="personal_api_key",
        resource_id=created.get("id"),
        details={"name": name},
        previous_value=None,
        new_value={"name": name, "key_prefix_sha256": key_prefix_sha256},
    )

    return {
        "success": True,
        "api_key": raw_key,
        "key": {
            "id": created.get("id"),
            "name": created.get("name"),
            "key_prefix": created.get("key_prefix"),
            "key_prefix_sha256": created.get("key_prefix_sha256"),
            "created_at": created.get("created_at"),
            "last_used_at": created.get("last_used_at"),
            "revoked_at": created.get("revoked_at"),
        },
    }


@router.delete("/api/settings/api-keys/{key_id}")
async def revoke_personal_api_key(
    key_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows = await postgrest_get(
        "personal_api_keys",
        (
            "select=id,name,revoked_at,key_prefix_sha256"
            f"&id=eq.{quote(key_id, safe='')}"
            f"&user_id=eq.{quote(user_id, safe='')}&limit=1"
        ),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="API key not found")

    key_row = rows[0]
    if key_row.get("revoked_at"):
        return {"success": True, "already_revoked": True}

    revoked_at = datetime.now(timezone.utc).isoformat()
    await postgrest_patch(
        "personal_api_keys",
        f"id=eq.{quote(key_id, safe='')}&user_id=eq.{quote(user_id, safe='')}",
        {"revoked_at": revoked_at},
    )

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action="revoke_personal_api_key",
        resource_type="personal_api_key",
        resource_id=key_id,
        details={"name": key_row.get("name")},
        previous_value={"revoked_at": None},
        new_value={"revoked_at": revoked_at, "key_prefix_sha256": key_row.get("key_prefix_sha256")},
    )
    return {"success": True}
