import re
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import (
    get_user_context,
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
)
from app.core.ssrf_validator import SSRFBlockedError, async_validate_webhook_url
from app.services.webhook_engine import encrypt_secret, generate_webhook_secret, hash_webhook_secret, emit_event

router = APIRouter()

_EVENT_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,62}$")


async def _require_tenant_admin(authorization: Optional[str]) -> dict[str, Any]:
    ctx = await get_user_context(authorization)
    role = ctx.get("role")
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    if role == "admin" and not ctx.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Admin user is not assigned to a tenant")
    return ctx


def _normalize_events(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="events must be a list of strings")
    out: list[str] = []
    for v in raw:
        s = str(v or "").strip().lower()
        if not s:
            continue
        if not _EVENT_RE.match(s):
            raise HTTPException(status_code=400, detail=f"Invalid event name: {s}")
        out.append(s)
    return sorted(set(out))


@router.get("/api/v1/webhooks")
async def list_webhooks(authorization: Optional[str] = Header(default=None)):
    ctx = await _require_tenant_admin(authorization)
    tenant_id = str(ctx.get("tenant_id") or "")
    role = ctx.get("role")
    query = "select=id,tenant_id,url,description,events,is_active,created_at,updated_at"
    if role == "global_admin" and not tenant_id:
        rows = await postgrest_get("webhooks", f"{query}&order=created_at.desc&limit=200")
    else:
        rows = await postgrest_get(
            "webhooks",
            f"{query}&tenant_id=eq.{quote(tenant_id, safe='')}&order=created_at.desc&limit=200",
        )
    return {"webhooks": rows}


async def _create_webhook_impl(request: Request, authorization: Optional[str]):
    ctx = await _require_tenant_admin(authorization)
    tenant_id = ctx.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    user_id = ctx.get("user_id")

    body = await request.json()
    url = str(body.get("url") or "").strip()
    if not url or len(url) > 2048:
        raise HTTPException(status_code=400, detail="url is required (max 2048 chars)")
    # SEC-01: HTTPS only. SEC-07: block RFC-1918 / loopback / link-local / IMDS.
    try:
        await async_validate_webhook_url(url)
    except SSRFBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    description = str(body.get("description") or "").strip()
    if len(description) > 240:
        raise HTTPException(status_code=400, detail="description must be 240 chars or fewer")
    events = _normalize_events(body.get("events"))

    hook_rows = await postgrest_insert(
        "webhooks",
        {
            "tenant_id": str(tenant_id),
            "url": url,
            "description": description or None,
            "events": events,
            "is_active": True,
            "created_by": user_id,
        },
    )
    if not hook_rows:
        raise HTTPException(status_code=500, detail="Failed to create webhook")
    hook = hook_rows[0]

    secret_value = generate_webhook_secret()
    await postgrest_insert(
        "webhook_secrets",
        {
            "tenant_id": str(tenant_id),
            "webhook_id": hook["id"],
            "secret_hash": hash_webhook_secret(secret_value),
            "encrypted_secret": encrypt_secret(secret_value),
            "is_active": True,
        },
    )

    return {
        "webhook": hook,
        "secret": secret_value,  # returned once; stored hashed+encrypted
        "note": "Copy this secret now. It cannot be retrieved later; rotate to generate a new one.",
    }


@router.post("/api/v1/webhooks")
async def create_webhook(request: Request, authorization: Optional[str] = Header(default=None)):
    return await _create_webhook_impl(request, authorization)


@router.post("/webhooks")
async def create_webhook_root_alias(request: Request, authorization: Optional[str] = Header(default=None)):
    """Spec alias: same behavior as POST /api/v1/webhooks."""
    return await _create_webhook_impl(request, authorization)


@router.patch("/api/v1/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, request: Request, authorization: Optional[str] = Header(default=None)):
    ctx = await _require_tenant_admin(authorization)
    tenant_id = str(ctx.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    rows = await postgrest_get(
        "webhooks",
        f"select=id,tenant_id&tenant_id=eq.{quote(tenant_id, safe='')}&id=eq.{quote(webhook_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Webhook not found")

    body = await request.json()
    patch: dict[str, Any] = {}
    if "url" in body:
        url = str(body.get("url") or "").strip()
        if not url or len(url) > 2048:
            raise HTTPException(status_code=400, detail="url is required (max 2048 chars)")
        try:
            await async_validate_webhook_url(url)
        except SSRFBlockedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        patch["url"] = url
    if "description" in body:
        description = str(body.get("description") or "").strip()
        if len(description) > 240:
            raise HTTPException(status_code=400, detail="description must be 240 chars or fewer")
        patch["description"] = description or None
    if "events" in body:
        patch["events"] = _normalize_events(body.get("events"))
    if "is_active" in body:
        patch["is_active"] = bool(body.get("is_active"))

    if not patch:
        return {"success": True, "webhook_id": webhook_id}

    await postgrest_patch("webhooks", f"id=eq.{quote(webhook_id, safe='')}", patch)
    return {"success": True, "webhook_id": webhook_id}


@router.delete("/api/v1/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, authorization: Optional[str] = Header(default=None)):
    ctx = await _require_tenant_admin(authorization)
    tenant_id = str(ctx.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    rows = await postgrest_get(
        "webhooks",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&id=eq.{quote(webhook_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await postgrest_delete("webhooks", f"id=eq.{quote(webhook_id, safe='')}")
    return {"success": True}


@router.post("/api/v1/webhooks/{webhook_id}/rotate-secret")
async def rotate_webhook_secret(webhook_id: str, authorization: Optional[str] = Header(default=None)):
    ctx = await _require_tenant_admin(authorization)
    tenant_id = str(ctx.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    hook_rows = await postgrest_get(
        "webhooks",
        f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}&id=eq.{quote(webhook_id, safe='')}&limit=1",
    )
    if not hook_rows:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Deactivate existing secrets (service role can bulk patch by webhook_id)
    await postgrest_patch(
        "webhook_secrets",
        f"tenant_id=eq.{quote(tenant_id, safe='')}&webhook_id=eq.{quote(webhook_id, safe='')}&is_active=eq.true",
        {"is_active": False},
    )

    new_secret = generate_webhook_secret()
    await postgrest_insert(
        "webhook_secrets",
        {
            "tenant_id": tenant_id,
            "webhook_id": webhook_id,
            "secret_hash": hash_webhook_secret(new_secret),
            "encrypted_secret": encrypt_secret(new_secret),
            "is_active": True,
        },
    )

    return {
        "success": True,
        "webhook_id": webhook_id,
        "secret": new_secret,
        "note": "Copy this secret now. It cannot be retrieved later; rotate again if lost.",
    }


@router.post("/api/v1/webhooks/test-event")
async def emit_test_event(request: Request, authorization: Optional[str] = Header(default=None)):
    """Admin-only test endpoint to emit a webhook event for the current tenant."""
    ctx = await _require_tenant_admin(authorization)
    tenant_id = ctx.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    body = await request.json()
    event_type = str(body.get("event_type") or "").strip().lower()
    if not event_type or not _EVENT_RE.match(event_type):
        raise HTTPException(status_code=400, detail="event_type is required (lowercase a-z0-9._-)")
    payload = body.get("payload")
    if payload is None or not isinstance(payload, dict):
        payload = {}

    event_id = await emit_event(str(tenant_id), event_type, payload)
    return {"success": True, "event_id": event_id}

