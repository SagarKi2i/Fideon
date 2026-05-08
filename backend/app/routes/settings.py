import asyncio
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
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
from app.services.tenant_activation_limits import distinct_tenant_activated_model_ids

router = APIRouter()
USER_PROFILE_NOT_FOUND = "User profile not found"

# ── Profile cache (30 s TTL per user) ────────────────────────────────────────
# Prevents redundant DB hits when the frontend calls /api/settings/profile
# multiple times in quick succession (realtime events, Strict Mode, etc.).
_PROFILE_CACHE: Dict[str, tuple[Dict[str, Any], float]] = {}
_PROFILE_TTL = 30.0


def _pcache_get(user_id: str) -> Optional[Dict[str, Any]]:
    entry = _PROFILE_CACHE.get(user_id)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    _PROFILE_CACHE.pop(user_id, None)
    return None


def _pcache_set(user_id: str, data: Dict[str, Any]) -> None:
    if len(_PROFILE_CACHE) > 1000:
        now = time.monotonic()
        stale = [k for k, (_, exp) in _PROFILE_CACHE.items() if exp < now]
        for k in stale:
            _PROFILE_CACHE.pop(k, None)
    _PROFILE_CACHE[user_id] = (data, time.monotonic() + _PROFILE_TTL)


def _pcache_invalidate(user_id: str) -> None:
    _PROFILE_CACHE.pop(user_id, None)


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

    cached = _pcache_get(user_id)
    if cached is not None:
        return cached

    # Fetch app_users row and role in parallel — role from JWT fast path if available.
    jwt_role = (user.get("app_metadata") or {}).get("role")
    rows_task = asyncio.create_task(postgrest_get(
        "app_users",
        f"select=user_id,email,full_name,metadata,tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    ))
    role_task = asyncio.create_task(_get_user_role(user_id)) if not jwt_role else None

    rows = await rows_task
    if not rows:
        raise HTTPException(status_code=404, detail=USER_PROFILE_NOT_FOUND)

    profile = rows[0]
    metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    preferences = _normalize_preferences(metadata)
    role = jwt_role or (await role_task if role_task else "user")
    tenant_name = None
    tenant_plan = None
    tenant_id = profile.get("tenant_id")
    tenant_agent_packs: Optional[list] = None
    tenant_max_active_models: Optional[int] = None
    tenant_distinct_activated_model_ids: list[str] = []
    if tenant_id:
        # Fetch tenant info and activated model IDs in parallel.
        tenant_rows, distinct_ids = await asyncio.gather(
            postgrest_get(
                "tenants",
                f"select=id,name,metadata,agent_packs,max_active_models&id=eq.{quote(str(tenant_id), safe='')}&limit=1",
            ),
            distinct_tenant_activated_model_ids(str(tenant_id)),
        )
        tenant_distinct_activated_model_ids = sorted(distinct_ids)
        if tenant_rows:
            tenant_row = tenant_rows[0]
            tenant_name = tenant_row.get("name")
            tenant_metadata = tenant_row.get("metadata") if isinstance(tenant_row.get("metadata"), dict) else {}
            tenant_plan = tenant_metadata.get("plan")
            packs = tenant_row.get("agent_packs")
            tenant_agent_packs = packs if isinstance(packs, list) else []
            raw_max = tenant_row.get("max_active_models")
            if raw_max is not None:
                try:
                    tenant_max_active_models = int(raw_max)
                except (TypeError, ValueError):
                    tenant_max_active_models = None
            else:
                tenant_max_active_models = None
    response = {
        "profile": {
            "user_id": profile.get("user_id"),
            "email": profile.get("email"),
            "full_name": profile.get("full_name") or "",
            "role": role or "user",
            "preferences": preferences,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "tenant_plan": tenant_plan,
            "tenant_agent_packs": tenant_agent_packs if tenant_agent_packs is not None else [],
            "tenant_max_active_models": tenant_max_active_models,
            "tenant_distinct_activated_model_ids": tenant_distinct_activated_model_ids,
        }
    }
    _pcache_set(user_id, response)
    return response


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
        raise HTTPException(status_code=404, detail=USER_PROFILE_NOT_FOUND)

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
    _pcache_invalidate(user_id)

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


@router.post("/api/settings/password-changed")
async def mark_password_changed(request: Request, authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    changed_at = datetime.now(timezone.utc).isoformat()
    rows = await postgrest_get(
        "app_users",
        f"select=metadata&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail=USER_PROFILE_NOT_FOUND)

    existing_metadata = rows[0].get("metadata")
    if not isinstance(existing_metadata, dict):
        existing_metadata = {}

    next_metadata = {
        **existing_metadata,
        "password_updated_at": changed_at,
    }

    await postgrest_patch(
        "app_users",
        f"user_id=eq.{quote(user_id, safe='')}",
        {
            "last_password_changed_at": changed_at,
            "metadata": next_metadata,
        },
    )

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action="password_changed",
        resource_type="app_user",
        resource_id=user_id,
        details={"password_changed": True},
        previous_value=None,
        new_value={"last_password_changed_at": changed_at},
    )

    return {"success": True, "last_password_changed_at": changed_at}


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
