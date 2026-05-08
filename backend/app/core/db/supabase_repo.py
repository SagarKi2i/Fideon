"""
Supabase/PostgREST implementation of DBRepository.

Translates DBQuery → PostgREST URL query string format.
Wraps the existing postgrest_* helpers in app.core.supabase.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from app.core.db.base import DBQuery, DBRepository


# ── Query translator ──────────────────────────────────────────────────────────

def _query_to_postgrest(query: DBQuery) -> str:
    """
    Translate a DBQuery into a PostgREST URL query string.

    DBQuery(filters={"user_id": "abc", "tenant_id": "xyz"}, select=["id","name"], limit=10)
    →  "user_id=eq.abc&tenant_id=eq.xyz&select=id,name&limit=10"
    """
    parts: list[str] = []

    # Equality filters
    for field, value in (query.filters or {}).items():
        if value is None:
            parts.append(f"{field}=is.null")
        else:
            parts.append(f"{field}=eq.{quote(str(value), safe='')}")

    # IN filters
    for field, values in (query.in_filters or {}).items():
        joined = ",".join(quote(str(v), safe="") for v in values)
        parts.append(f"{field}=in.({joined})")

    # GT / LT / GTE / LTE filters
    for field, value in (query.gt_filters or {}).items():
        parts.append(f"{field}=gt.{quote(str(value), safe='')}")
    for field, value in (query.lt_filters or {}).items():
        parts.append(f"{field}=lt.{quote(str(value), safe='')}")
    for field, value in (query.gte_filters or {}).items():
        parts.append(f"{field}=gte.{quote(str(value), safe='')}")
    for field, value in (query.lte_filters or {}).items():
        parts.append(f"{field}=lte.{quote(str(value), safe='')}")

    # Column selection
    if query.select:
        parts.append(f"select={','.join(query.select)}")

    # Ordering
    if query.order_by:
        col = query.order_by.lstrip("-")
        direction = "desc" if query.order_by.startswith("-") else "asc"
        parts.append(f"order={col}.{direction}")

    # Limit / offset
    if query.limit is not None:
        parts.append(f"limit={query.limit}")
    if query.offset is not None:
        parts.append(f"offset={query.offset}")

    return "&".join(parts)


# ── Service headers ────────────────────────────────────────────────────────────

def _service_headers(json_body: bool = True) -> dict[str, str]:
    h = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


# ── SupabaseRepository ────────────────────────────────────────────────────────

class SupabaseRepository(DBRepository):
    """
    Supabase PostgREST + GoTrue implementation.
    This is the active default backend (DB_BACKEND=supabase).
    """

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def get(self, table: str, query: DBQuery) -> List[Dict[str, Any]]:
        qs = _query_to_postgrest(query)
        url = f"{SUPABASE_URL}/rest/v1/{table}" + (f"?{qs}" if qs else "")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=_service_headers(json_body=False))
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)
        return resp.json()

    async def get_one(self, table: str, query: DBQuery) -> Optional[Dict[str, Any]]:
        q = DBQuery(
            filters=query.filters,
            in_filters=query.in_filters,
            gt_filters=query.gt_filters,
            lt_filters=query.lt_filters,
            select=query.select,
            order_by=query.order_by,
            limit=1,
        )
        rows = await self.get(table, q)
        return rows[0] if rows else None

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = _service_headers()
        headers["Prefer"] = "return=representation"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                content=json.dumps(data),
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)
        rows = resp.json()
        return rows[0] if isinstance(rows, list) and rows else rows

    async def insert_many(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        headers = _service_headers()
        headers["Prefer"] = "return=representation"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                content=json.dumps(rows),
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)
        return resp.json()

    async def update(self, table: str, query: DBQuery, data: Dict[str, Any]) -> None:
        qs = _query_to_postgrest(query)
        url = f"{SUPABASE_URL}/rest/v1/{table}" + (f"?{qs}" if qs else "")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(url, headers=_service_headers(), content=json.dumps(data))
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)

    async def delete(self, table: str, query: DBQuery) -> None:
        qs = _query_to_postgrest(query)
        url = f"{SUPABASE_URL}/rest/v1/{table}" + (f"?{qs}" if qs else "")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(url, headers=_service_headers(json_body=False))
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)

    async def count(self, table: str, query: DBQuery) -> int:
        qs = _query_to_postgrest(query)
        url = f"{SUPABASE_URL}/rest/v1/{table}" + (f"?{qs}" if qs else "")
        headers = _service_headers(json_body=False)
        headers["Prefer"] = "count=exact"
        headers["Range-Unit"] = "items"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.head(url, headers=headers)
        content_range = resp.headers.get("content-range", "")
        # content-range: 0-9/42  → total is 42
        try:
            return int(content_range.split("/")[-1])
        except (ValueError, IndexError):
            return 0

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def verify_user(self, token: str) -> Dict[str, Any]:
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

    async def admin_list_users(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers=_service_headers(json_body=False),
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)
        return resp.json().get("users", [])
