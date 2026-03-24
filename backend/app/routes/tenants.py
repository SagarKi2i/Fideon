"""POST /api/v1/tenants — Tenant provisioning endpoint (FNF-48).

Creates a tenant record and a default admin user in a single request.
< 3 s end-to-end on a warm Supabase connection.

Auth: Bearer token of an existing admin or global_admin user.

Request body:
    name            str  required  Human-readable tenant display name
    plan            str  optional  starter | growth | enterprise  (default: starter)
    slug            str  optional  Custom slug; auto-generated from name if omitted
    admin_email     str  required  Email for the default admin user
    admin_password  str  required  Password for the default admin user (min 8 chars)
    admin_full_name str  optional  Display name for the default admin user
    metadata        obj  optional  Extra JSONB stored on the tenant row

Response:
    { success, tenant: { id, slug, name, plan, is_active, created_at },
               admin_user: { id, email, full_name, role } }
"""

import json
import re
import uuid
from asyncio import sleep
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
import structlog

from app.core.config import SUPABASE_URL
from app.core.limiter import limiter
from app.core.supabase import (
    get_user_context,
    insert_audit_log,
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
)

router = APIRouter()
log = structlog.get_logger("tenants")

_VALID_PLANS = {"starter", "growth", "enterprise"}
# Custom slug: lowercase, alphanumeric + hyphens, min 3 chars, no leading/trailing hyphen.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]+[a-z0-9]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")


@router.get("/api/v1/auth/email-availability")
@limiter.limit("30/minute")
async def check_email_availability(
    request: Request,  # required by slowapi
    email: str = Query(..., min_length=6, max_length=254),
):
    normalized_email = email.strip().lower()
    if not _EMAIL_RE.match(normalized_email):
        raise HTTPException(status_code=400, detail="'email' is not a valid email address")

    rows = await postgrest_get(
        "app_users",
        f"select=user_id&email=eq.{quote(normalized_email, safe='')}&limit=1",
    )
    return {"email": normalized_email, "exists": bool(rows)}


def _auto_slug(name: str, suffix: str) -> str:
    """Derive a URL-safe slug from *name*, appended with *suffix* for uniqueness.

    Mirrors the SQL normalisation in the DB trigger:
        lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))
    """
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "tenant"
    return f"{base}-{suffix}"


async def _require_admin(authorization: Optional[str]) -> dict:
    """Return the verified requester dict or raise 401/403."""
    context = await get_user_context(authorization)
    role = context.get("role")
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    if role == "admin" and not context.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Admin user is not assigned to a tenant")
    return context


async def _delete_auth_user(user_id: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{quote(user_id, safe='')}",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Failed to rollback auth user: {resp.text}")


async def _rollback_provisioning(tenant_id: Optional[str], admin_user_id: Optional[str]) -> None:
    rollback_errors: list[str] = []
    if admin_user_id:
        try:
            await _delete_auth_user(admin_user_id)
        except Exception as exc:  # noqa: BLE001
            rollback_errors.append(f"auth_user={exc}")
    if tenant_id:
        try:
            await postgrest_delete("tenants", f"id=eq.{quote(tenant_id, safe='')}")
        except Exception as exc:  # noqa: BLE001
            rollback_errors.append(f"tenant={exc}")
    if rollback_errors:
        log.error("tenants.rollback_failed", errors=rollback_errors, tenant_id=tenant_id, admin_user_id=admin_user_id)
        raise HTTPException(
            status_code=500,
            detail=(
                "Tenant provisioning failed and rollback was incomplete. "
                "Please contact support with server logs."
            ),
        )


async def _link_admin_user_to_tenant(admin_user_id: str, tenant_id: str, admin_full_name: str) -> None:
    link_payload: dict = {"tenant_id": tenant_id}
    if admin_full_name:
        link_payload["full_name"] = admin_full_name

    # DB trigger inserts app_users asynchronously; retry briefly before failing.
    for _ in range(6):
        rows = await postgrest_get(
            "app_users",
            f"select=user_id&user_id=eq.{quote(admin_user_id, safe='')}&limit=1",
        )
        if rows:
            await postgrest_patch(
                "app_users",
                f"user_id=eq.{quote(admin_user_id, safe='')}",
                link_payload,
            )
            return
        await sleep(0.25)

    raise HTTPException(
        status_code=500,
        detail="Failed to link admin user to tenant profile",
    )


async def _upsert_admin_role(admin_user_id: str) -> None:
    headers = service_headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/user_roles?on_conflict=user_id",
            headers=headers,
            content=json.dumps([{"user_id": admin_user_id, "role": "admin"}]),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Failed to assign admin role: {resp.text}")


def _extract_idempotency_key(
    x_idempotency_key: Optional[str], body: dict, metadata: dict
) -> Optional[str]:
    candidates = [
        (x_idempotency_key or "").strip(),
        str(body.get("idempotency_key") or "").strip(),
        str(metadata.get("idempotency_key") or "").strip() if isinstance(metadata, dict) else "",
    ]
    for candidate in candidates:
        if candidate:
            if not _IDEMPOTENCY_KEY_RE.match(candidate):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "'idempotency_key' must be 8-128 chars using letters, "
                        "numbers, underscore, hyphen, colon, or dot"
                    ),
                )
            return candidate
    return None


def _extract_tenant_input_fields(body: dict) -> tuple[str, str, str, str, str, str, dict]:
    name: str = (body.get("name") or "").strip()
    plan: str = (body.get("plan") or "starter").strip().lower()
    custom_slug: str = (body.get("slug") or "").strip().lower()
    admin_email: str = (body.get("admin_email") or "").strip().lower()
    admin_password: str = body.get("admin_password") or ""
    admin_full_name: str = (body.get("admin_full_name") or "").strip()
    extra_metadata = body.get("metadata") or {}
    return name, plan, custom_slug, admin_email, admin_password, admin_full_name, extra_metadata


def _validate_tenant_input(
    name: str,
    plan: str,
    admin_email: str,
    admin_password: str,
    extra_metadata: dict,
) -> None:
    if not name:
        raise HTTPException(status_code=400, detail="'name' is required")
    if plan not in _VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"'plan' must be one of: {', '.join(sorted(_VALID_PLANS))}",
        )
    if not admin_email:
        raise HTTPException(status_code=400, detail="'admin_email' is required")
    if not _EMAIL_RE.match(admin_email):
        raise HTTPException(status_code=400, detail="'admin_email' is not a valid email address")
    if not admin_password:
        raise HTTPException(status_code=400, detail="'admin_password' is required")
    if len(admin_password) < 8:
        raise HTTPException(
            status_code=400, detail="'admin_password' must be at least 8 characters"
        )
    if not isinstance(extra_metadata, dict):
        raise HTTPException(status_code=400, detail="'metadata' must be an object")


async def _find_tenant_by_idempotency_key(key: str) -> Optional[dict]:
    rows = await postgrest_get(
        "tenants",
        (
            "select=id,slug,name,is_active,created_at,metadata"
            f"&metadata->>provisioning_idempotency_key=eq.{quote(key, safe='')}&limit=1"
        ),
    )
    return rows[0] if rows else None


async def _idempotent_replay_response_or_none(
    idempotency_key: Optional[str],
    requester_id: str,
) -> Optional[JSONResponse]:
    if not idempotency_key:
        return None
    replay_tenant = await _find_tenant_by_idempotency_key(idempotency_key)
    if not replay_tenant:
        return None
    metadata = replay_tenant.get("metadata") or {}
    if metadata.get("provisioned_by") != requester_id:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key already used by another requester",
        )
    log.info("tenants.create.idempotent_replay", tenant_id=replay_tenant["id"], requester_id=requester_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "idempotent_replay": True,
            "tenant": {
                "id": replay_tenant["id"],
                "slug": replay_tenant["slug"],
                "name": replay_tenant["name"],
                "plan": metadata.get("plan", "starter"),
                "is_active": replay_tenant.get("is_active", True),
                "created_at": replay_tenant.get("created_at"),
            },
            "admin_user": {
                "id": metadata.get("admin_user_id"),
                "email": metadata.get("admin_email"),
                "full_name": metadata.get("admin_full_name"),
                "role": "admin",
            },
        },
    )


def _resolve_slug_or_fail(custom_slug: str, name: str) -> str:
    if custom_slug:
        if not _SLUG_RE.match(custom_slug):
            raise HTTPException(
                status_code=400,
                detail="'slug' must be lowercase alphanumeric with hyphens, min 3 chars, "
                       "no leading/trailing hyphens",
            )
        return custom_slug
    return _auto_slug(name, str(uuid.uuid4())[:8])


async def _ensure_slug_available(slug: str) -> None:
    existing = await postgrest_get(
        "tenants", f"select=id&slug=eq.{quote(slug, safe='')}&limit=1"
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Tenant slug '{slug}' is already taken"
        )


async def _create_tenant_row_or_raise(slug: str, name: str, tenant_metadata: dict) -> dict:
    try:
        rows = await postgrest_insert(
            "tenants",
            {
                "slug": slug,
                "name": name,
                "is_active": True,
                "metadata": tenant_metadata,
            },
        )
    except HTTPException as exc:
        detail = str(exc.detail)
        if "23505" in detail or "duplicate" in detail.lower():
            raise HTTPException(
                status_code=409, detail=f"Tenant slug '{slug}' is already taken"
            )
        raise
    return rows[0]


async def _create_admin_auth_user_or_rollback(
    tenant_id: str,
    admin_email: str,
    admin_password: str,
    admin_full_name: str,
    plan: str,
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        auth_resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(),
            content=json.dumps(
                {
                    "email": admin_email,
                    "password": admin_password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": admin_full_name or "",
                        "requested_role": "admin",
                        "plan": plan,
                    },
                }
            ),
        )
    if auth_resp.status_code >= 400:
        log.warning("tenants.create.auth_user_failed", tenant_id=tenant_id, status_code=auth_resp.status_code)
        await _rollback_provisioning(tenant_id=tenant_id, admin_user_id=None)
        error_body = auth_resp.text
        if "already registered" in error_body or "already exists" in error_body:
            raise HTTPException(
                status_code=409,
                detail=f"A user with email '{admin_email}' already exists",
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to create admin user: {error_body}"
        )
    return auth_resp.json()


@router.post("/api/v1/tenants", status_code=201)
@limiter.limit("5/minute")
async def create_tenant(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_idempotency_key: Optional[str] = Header(default=None),
):
    requester_context = await _require_admin(authorization)
    requester_id = requester_context["user_id"]
    requester_role = requester_context["role"]
    log.info("tenants.create.start", requester_id=requester_id, requester_role=requester_role)

    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    name, plan, custom_slug, admin_email, admin_password, admin_full_name, extra_metadata = _extract_tenant_input_fields(body)
    _validate_tenant_input(name, plan, admin_email, admin_password, extra_metadata)
    idempotency_key = _extract_idempotency_key(x_idempotency_key, body, extra_metadata)
    replay = await _idempotent_replay_response_or_none(idempotency_key, requester_id)
    if replay:
        return replay

    # ── Slug resolution ──────────────────────────────────────────────────────
    slug = _resolve_slug_or_fail(custom_slug, name)

    # ── Duplicate-slug check ─────────────────────────────────────────────────
    await _ensure_slug_available(slug)

    # ── 1. Create tenant row ─────────────────────────────────────────────────
    tenant_metadata = {
        "plan": plan,
        "provisioned_by": requester_id,
        "provisioned_by_role": requester_role,
        "provisioning_idempotency_key": idempotency_key,
        **extra_metadata,
    }
    tenant = await _create_tenant_row_or_raise(slug, name, tenant_metadata)
    tenant_id: str = tenant["id"]
    admin_user_id: Optional[str] = None

    # ── 2. Create default admin user via Supabase Auth admin API ─────────────
    # We deliberately omit 'tenant_name' from user_metadata so the DB trigger
    # (handle_new_app_user) does NOT create a second tenant row.  We link the
    # user to the already-created tenant explicitly in step 3.
    auth_user = await _create_admin_auth_user_or_rollback(
        tenant_id, admin_email, admin_password, admin_full_name, plan
    )
    admin_user_id = auth_user["id"]

    # ── 3. Link admin user → tenant in app_users ─────────────────────────────
    try:
        await _link_admin_user_to_tenant(admin_user_id, tenant_id, admin_full_name)
        # ── 4. Assign admin role ─────────────────────────────────────────────
        # Upsert so this is idempotent if the trigger already inserted a role row.
        await _upsert_admin_role(admin_user_id)
        await postgrest_patch(
            "tenants",
            f"id=eq.{quote(tenant_id, safe='')}",
            {
                "metadata": {
                    **tenant_metadata,
                    "admin_user_id": admin_user_id,
                    "admin_email": admin_email,
                    "admin_full_name": admin_full_name or None,
                }
            },
        )
    except HTTPException:
        await _rollback_provisioning(tenant_id=tenant_id, admin_user_id=admin_user_id)
        raise

    # ── 5. Audit log ─────────────────────────────────────────────────────────
    await insert_audit_log(
        request=request,
        user_id=requester_id,
        action="create_tenant",
        resource_type="tenant",
        resource_id=tenant_id,
        details={"slug": slug, "plan": plan, "admin_user_id": admin_user_id},
        previous_value=None,
        new_value={"slug": slug, "name": name, "plan": plan, "is_active": True},
    )

    return {
        "success": True,
        "tenant": {
            "id": tenant_id,
            "slug": slug,
            "name": name,
            "plan": plan,
            "is_active": True,
            "created_at": tenant.get("created_at"),
        },
        "admin_user": {
            "id": admin_user_id,
            "email": admin_email,
            "full_name": admin_full_name or None,
            "role": "admin",
        },
    }
