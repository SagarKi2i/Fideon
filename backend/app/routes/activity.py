import asyncio
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from app.core.supabase import postgrest_get, verify_user

router = APIRouter()

PAGE_SIZE = 25

_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}

# PostgREST: commas inside `in.(...)` must be `%2C` when the clause appears inside `or=(...)`,
# otherwise the parser splits on those commas and the filter returns wrong/empty results.
_SAFE_POSTGREST_OR = "(),:%-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ._"


def _admin_tenant_or_user_ids_filter(tenant_id: str, user_ids: list[str]) -> str:
    tid = str(tenant_id)
    in_list = "%2C".join(str(u) for u in user_ids)
    or_expr = f"(tenant_id.eq.{tid},user_id.in.({in_list}))"
    return quote(or_expr, safe=_SAFE_POSTGREST_OR)


async def _get_user_role(authorization: Optional[str]) -> tuple[dict, Optional[str], Optional[str]]:
    user = await verify_user(authorization)
    uid = quote(user["id"], safe="")
    roles_task = postgrest_get(
        "user_roles", f"select=role&user_id=eq.{uid}&limit=1"
    )
    profiles_task = postgrest_get(
        "app_users", f"select=tenant_id&user_id=eq.{uid}&limit=1"
    )
    roles, profiles = await asyncio.gather(roles_task, profiles_task)
    role = roles[0].get("role") if roles else None
    tenant_id = profiles[0].get("tenant_id") if profiles else None
    return user, role, tenant_id


@router.get("/api/activity/system")
async def get_system_activity(
    page: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Return paginated rows from audit_logs (tenant-scoped for admins).

    - global_admin / admin: rows where audit_logs.tenant_id equals the requester's tenant
    - user / viewer: only rows for their own user_id
    - guest: denied
    """
    user, role, tenant_id = await _get_user_role(authorization)
    if role not in {"global_admin", "admin", "user", "viewer"}:
        raise HTTPException(status_code=403, detail="Access denied")

    offset = page * PAGE_SIZE
    # Fetch one extra row to detect if there is a next page.
    limit = PAGE_SIZE + 1

    # List view: omit heavy JSONB blobs (prediction/shap/details/previous/new_value) — they
    # dominated payload size and slow TTFB + JSON parse for admins on busy tenants.
    query = (
        "select=id,user_id,action,resource_type,resource_id,"
        "ip_address,user_agent,model_id,reasoning,created_at"
    )
    query += f"&order=created_at.desc&limit={limit}&offset={offset}"

    # Users/viewers see only their own rows.
    if role not in {"global_admin", "admin"}:
        query += f"&user_id=eq.{quote(user['id'], safe='')}"
    else:
        # Tenant admins/global_admin are tenant-bounded in this project.
        if not tenant_id:
            raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
        tid_q = quote(str(tenant_id), safe="")
        # Rows tagged with tenant_id OR legacy rows (tenant_id null) for users in this tenant.
        # Without the OR branch, older audit_logs before backfill show as empty in the UI.
        tenant_users = await postgrest_get(
            "app_users",
            f"select=user_id&tenant_id=eq.{tid_q}",
        )
        tenant_user_ids = [str(r["user_id"]) for r in tenant_users if r.get("user_id")]
        max_ids_for_or = 80
        if tenant_user_ids and len(tenant_user_ids) <= max_ids_for_or:
            query += f"&or={_admin_tenant_or_user_ids_filter(str(tenant_id), tenant_user_ids)}"
        else:
            query += f"&tenant_id=eq.{tid_q}"

    if action:
        query += f"&action=ilike.*{quote(action, safe='')}*"
    if resource_type:
        query += f"&resource_type=eq.{quote(resource_type, safe='')}"
    if date_from:
        query += f"&created_at=gte.{quote(date_from, safe='')}"
    if date_to:
        query += f"&created_at=lte.{quote(date_to, safe='')}"

    rows = await postgrest_get("audit_logs", query)
    has_more = len(rows) > PAGE_SIZE
    if has_more:
        rows = rows[:PAGE_SIZE]

    return JSONResponse(
        content={"logs": rows, "page": page, "page_size": PAGE_SIZE, "has_more": has_more},
        headers=_NO_CACHE,
    )


@router.get("/api/activity/auth")
async def get_auth_activity(
    page: int = 0,
    event: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Return paginated rows from auth_audit with tenant isolation."""
    user, role, tenant_id = await _get_user_role(authorization)
    if role not in {"global_admin", "admin", "user", "viewer"}:
        raise HTTPException(status_code=403, detail="Access denied")

    offset = page * PAGE_SIZE
    limit = PAGE_SIZE + 1

    query = (
        "select=id,user_id,email,role,event,action_code,outcome_code,resource_type,resource_id,created_at"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )

    if role not in {"global_admin", "admin"}:
        query += f"&user_id=eq.{quote(user['id'], safe='')}"
    else:
        if not tenant_id:
            raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
        tid_q = quote(str(tenant_id), safe="")
        tenant_users = await postgrest_get(
            "app_users",
            f"select=user_id&tenant_id=eq.{tid_q}",
        )
        tenant_user_ids = [str(r["user_id"]) for r in tenant_users if r.get("user_id")]
        max_ids_for_or = 80
        if tenant_user_ids and len(tenant_user_ids) <= max_ids_for_or:
            query += f"&or={_admin_tenant_or_user_ids_filter(str(tenant_id), tenant_user_ids)}"
        else:
            query += f"&tenant_id=eq.{tid_q}"

    if event:
        query += f"&event=ilike.*{quote(event, safe='')}*"
    if date_from:
        query += f"&created_at=gte.{quote(date_from, safe='')}"
    if date_to:
        query += f"&created_at=lte.{quote(date_to, safe='')}"

    rows = await postgrest_get("auth_audit", query)
    has_more = len(rows) > PAGE_SIZE
    if has_more:
        rows = rows[:PAGE_SIZE]

    return JSONResponse(
        content={"logs": rows, "page": page, "page_size": PAGE_SIZE, "has_more": has_more},
        headers=_NO_CACHE,
    )
