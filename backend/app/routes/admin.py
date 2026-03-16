import json
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import (
    admin_list_users,
    insert_audit_log,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
    verify_user,
)

router = APIRouter()
VALID_ROLES = {"global_admin", "admin", "user", "viewer", "guest"}


async def _get_requester_role(authorization: Optional[str]) -> tuple[dict, Optional[str]]:
    requester = await verify_user(authorization)
    requester_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_role = requester_roles[0].get("role") if requester_roles else None
    return requester, requester_role


@router.get("/api/list-users")
async def list_users(authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    roles = await postgrest_get("user_roles", f"select=role&user_id=eq.{quote(user['id'], safe='')}&limit=1")
    if not roles or roles[0].get("role") not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")

    users = await admin_list_users()
    user_roles = await postgrest_get("user_roles", "select=user_id,role")
    role_map = {r["user_id"]: r["role"] for r in user_roles}
    out = [
        {
            "id": u.get("id"),
            "email": u.get("email"),
            "role": role_map.get(u.get("id"), "user"),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]
    return {"users": out}


@router.post("/api/admin-create-user")
async def admin_create_user(request: Request, authorization: Optional[str] = Header(default=None)):
    requester, requester_role = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    email = body.get("email")
    password = body.get("password")
    full_name = body.get("full_name")
    role = body.get("role", "user")
    action = body.get("action", "create")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    if action == "update_password":
        users = await admin_list_users()
        user = next((u for u in users if u.get("email") == email), None)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{SUPABASE_URL}/auth/v1/admin/users/{user['id']}",
                headers=service_headers(),
                content=json.dumps({"password": password}),
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=resp.text)
        # Never store previous/new password values — both are None.
        await insert_audit_log(
            request=request,
            user_id=requester["id"],
            action="update_password",
            resource_type="user",
            resource_id=user["id"],
            previous_value=None,
            new_value=None,
        )
        return {"success": True, "message": "Password updated successfully"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(),
            content=json.dumps(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": full_name or "",
                        "requested_role": role,
                    },
                }
            ),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.text)
    user_data = resp.json().get("user")
    if user_data:
        try:
            await postgrest_insert("user_roles", {"user_id": user_data["id"], "role": role})
        except Exception:
            pass
        if full_name:
            try:
                await postgrest_patch(
                    "app_users",
                    f"user_id=eq.{quote(user_data['id'], safe='')}",
                    {"full_name": full_name},
                )
            except Exception:
                pass
        await insert_audit_log(
            request=request,
            user_id=requester["id"],
            action="create_user",
            resource_type="user",
            resource_id=user_data["id"],
            details={"role": role},
            previous_value=None,                   # new user — no prior state
            new_value={"role": role},
        )
    return {"success": True, "user": {"id": user_data.get("id"), "email": user_data.get("email")}}


@router.post("/api/admin-set-user-role")
async def admin_set_user_role(request: Request, authorization: Optional[str] = Header(default=None)):
    requester, requester_role = await _get_requester_role(authorization)
    if requester_role != "global_admin":
        raise HTTPException(status_code=403, detail="Global admin access required")

    body = await request.json()
    user_id = body.get("user_id")
    role = body.get("role")
    if not user_id or role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Valid user_id and role are required")

    # Fetch the current role BEFORE the update so we can record the previous value.
    current_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1"
    )
    old_role = current_roles[0].get("role") if current_roles else None

    headers = service_headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/user_roles?on_conflict=user_id",
            headers=headers,
            content=json.dumps([{"user_id": user_id, "role": role}]),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.text)

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="set_user_role",
        resource_type="user_role",
        resource_id=user_id,
        details={"role": role},
        previous_value={"role": old_role} if old_role else None,
        new_value={"role": role},
    )
    return {"success": True, "user_id": user_id, "role": role}
