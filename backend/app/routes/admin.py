import json
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import admin_list_users, postgrest_get, postgrest_insert, service_headers, verify_user

router = APIRouter()
VALID_ROLES = {"global_admin", "admin", "user", "viewer", "guest"}


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
async def admin_create_user(request: Request):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")
    role = body.get("role", "user")
    action = body.get("action", "create")
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
        return {"success": True, "message": "Password updated successfully"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(),
            content=json.dumps({"email": email, "password": password, "email_confirm": True}),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.text)
    user_data = resp.json().get("user")
    if user_data:
        try:
            await postgrest_insert("user_roles", {"user_id": user_data["id"], "role": role})
        except Exception:
            pass
    return {"success": True, "user": {"id": user_data.get("id"), "email": user_data.get("email")}}


@router.post("/api/admin-set-user-role")
async def admin_set_user_role(request: Request, authorization: Optional[str] = Header(default=None)):
    requester = await verify_user(authorization)
    requester_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_role = requester_roles[0].get("role") if requester_roles else None
    if requester_role != "global_admin":
        raise HTTPException(status_code=403, detail="Global admin access required")

    body = await request.json()
    user_id = body.get("user_id")
    role = body.get("role")
    if not user_id or role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Valid user_id and role are required")

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

    return {"success": True, "user_id": user_id, "role": role}
