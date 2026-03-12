import json
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import admin_list_users, postgrest_get, postgrest_insert, service_headers, verify_user

router = APIRouter()


@router.get("/api/list-users")
async def list_users(authorization: Optional[str] = Header(default=None)):
    user = await verify_user(authorization)
    roles = await postgrest_get("user_roles", f"select=role&user_id=eq.{quote(user['id'], safe='')}&limit=1")
    if not roles or roles[0].get("role") != "admin":
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
