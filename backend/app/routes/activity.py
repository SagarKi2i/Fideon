from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException

from app.core.supabase import postgrest_get, verify_user

router = APIRouter()

PAGE_SIZE = 25


async def _get_user_role(authorization: Optional[str]) -> tuple[dict, Optional[str]]:
    user = await verify_user(authorization)
    roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(user['id'], safe='')}&limit=1"
    )
    role = roles[0].get("role") if roles else None
    return user, role


@router.get("/api/activity/system")
async def get_system_activity(
    page: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Return paginated rows from audit_logs.

    - global_admin / admin: all rows
    - user / viewer: only their own rows
    - guest: denied
    """
    user, role = await _get_user_role(authorization)
    if role not in {"global_admin", "admin", "user", "viewer"}:
        raise HTTPException(status_code=403, detail="Access denied")

    offset = page * PAGE_SIZE
    # Fetch one extra row to detect if there is a next page.
    limit = PAGE_SIZE + 1

    query = (
        "select=id,user_id,action,resource_type,resource_id,details,"
        "ip_address,user_agent,previous_value,new_value,"
        "model_id,prediction,shap_values,reasoning,"
        "integrity_hash,chain_hash,sequence_num,created_at"
    )
    query += f"&order=created_at.desc&limit={limit}&offset={offset}"

    # Non-admins see only their own rows (defence-in-depth; RLS also enforces this).
    if role not in {"global_admin", "admin"}:
        query += f"&user_id=eq.{quote(user['id'], safe='')}"

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

    return {"logs": rows, "page": page, "page_size": PAGE_SIZE, "has_more": has_more}
