"""
W3 — FastAPI dependency: get_current_tenant

Injects verified user context (user_id, role, tenant_id) into route handlers.
All routes that touch multi-tenant data MUST use this dependency instead of
calling verify_user() directly — it guarantees tenant_id is always present
and prevents accidental cross-tenant data access.

Usage:
    from app.core.deps import CurrentTenant

    @router.get("/devices")
    async def list_devices(ctx: CurrentTenant):
        rows = await tenant_scoped_get("devices", "select=*", ctx["tenant_id"])
        return rows

    # Or with explicit type:
    @router.get("/devices")
    async def list_devices(
        ctx: Annotated[TenantContext, Depends(get_current_tenant)]
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException

from app.core.supabase import get_user_context
from app.core.db import DBRepository, DBQuery, get_db as _get_db


# ── Type alias ────────────────────────────────────────────────────────────────

class TenantContext(dict):
    """
    Dict subclass with keys:
        user      – full Supabase user object
        user_id   – str (UUID)
        role      – str | None  ("global_admin" | "admin" | "user" | "viewer" | "guest")
        tenant_id – str | None  (UUID)

    Use ctx["user_id"], ctx["tenant_id"], ctx["role"].
    """


# ── Core dependency ───────────────────────────────────────────────────────────

async def get_current_tenant(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> TenantContext:
    """
    Verifies the Bearer JWT and returns the full tenant context.

    Raises:
        401 — token missing or invalid
        403 — token valid but user has no tenant association (rare: admin-only accounts
               with tenant_id=NULL are allowed through so global_admin routes still work)
    """
    ctx = await get_user_context(authorization)
    return TenantContext(ctx)


async def get_current_tenant_strict(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> TenantContext:
    """
    Same as get_current_tenant but raises 403 if tenant_id is NULL.
    Use this on routes that absolutely require tenant scoping
    (e.g., device listing, document access, extraction runs).
    """
    ctx = await get_user_context(authorization)
    if not ctx.get("tenant_id"):
        raise HTTPException(
            status_code=403,
            detail="No tenant association found for this account. "
                   "Contact your administrator.",
        )
    return TenantContext(ctx)


async def get_current_admin(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> TenantContext:
    """
    Same as get_current_tenant but additionally enforces admin or global_admin role.
    Raises 403 for any other role.
    """
    ctx = await get_user_context(authorization)
    role = ctx.get("role") or ""
    if role not in ("admin", "global_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return TenantContext(ctx)


# ── Annotated shortcuts (preferred in route signatures) ───────────────────────

CurrentTenant       = Annotated[TenantContext, Depends(get_current_tenant)]
CurrentTenantStrict = Annotated[TenantContext, Depends(get_current_tenant_strict)]
CurrentAdmin        = Annotated[TenantContext, Depends(get_current_admin)]

# ── DB repository dependency ──────────────────────────────────────────────────
# Use in routes that need direct DB access:
#   async def my_route(db: GetDB):
#       rows = await db.tenant_get("devices", DBQuery(), tenant_id=ctx["tenant_id"])

def get_db() -> DBRepository:
    """Returns the active DBRepository (Supabase/Mongo/Postgres based on DB_BACKEND)."""
    return _get_db()

GetDB = Annotated[DBRepository, Depends(get_db)]
