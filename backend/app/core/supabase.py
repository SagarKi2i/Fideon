import json
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from .config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def service_headers(json_body: bool = True) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


async def verify_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return resp.json()


async def postgrest_get(table: str, query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json()


async def postgrest_insert(table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    headers = service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json()


async def postgrest_patch(table: str, query: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(),
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)


async def postgrest_delete(table: str, query: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)


async def get_device_by_token(device_token: str) -> Dict[str, Any]:
    encoded = quote(device_token, safe="")
    rows = await postgrest_get("devices", f"select=*&device_token=eq.{encoded}&limit=1")
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid device token")
    device = rows[0]
    if not device.get("is_active", False):
        raise HTTPException(status_code=403, detail="Device is deactivated")
    return device


async def admin_list_users() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json().get("users", [])
