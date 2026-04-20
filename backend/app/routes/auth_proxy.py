"""
Auth proxy — routes login / logout / refresh / signup through FastAPI so the
frontend never calls Supabase GoTrue directly.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_ANON_KEY, SUPABASE_URL
from app.core.limiter import limiter
from app.core.supabase import (
    insert_auth_audit_row,
    postgrest_get,
    postgrest_patch,
    service_headers,
    verify_user,
)

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _anon_headers() -> dict:
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }


async def _resolve_role(user_id: str) -> str:
    try:
        rows = await postgrest_get(
            "user_roles",
            f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1",
        )
        return rows[0].get("role", "user") if rows else "user"
    except Exception:
        return "user"


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/api/v1/auth/login")
@limiter.limit("10/minute")
async def login(request: Request):
    """Proxy sign-in to Supabase GoTrue. Returns session tokens to the client."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")

    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=_anon_headers(),
            content=json.dumps({"email": email, "password": password}),
        )

    if resp.status_code >= 400:
        data = resp.json() if resp.content else {}
        msg = data.get("error_description") or data.get("error") or "Invalid login credentials"
        raise HTTPException(status_code=401, detail=msg)

    data = resp.json()
    user = data.get("user") or {}
    user_id = user.get("id")
    role = "user"

    if user_id:
        role = await _resolve_role(user_id)
        await insert_auth_audit_row(
            user_id=user_id,
            email=email,
            role=role,
            event="login",
            action_code="E",
            outcome_code=0,
            resource_type="auth_session",
            resource_id=None,
        )

    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type", "bearer"),
        "user": user,
        "role": role,
    }


# ─── Logout ──────────────────────────────────────────────────────────────────

@router.post("/api/v1/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    """Proxy sign-out to Supabase GoTrue and write an audit row."""
    if not authorization or not authorization.lower().startswith("bearer "):
        # Best-effort: caller may already be locally signed out.
        return {"success": True}

    token = authorization.split(" ", 1)[1]

    # Resolve user before invalidating the token.
    user_id = None
    email = ""
    role = "user"
    try:
        user_info = await verify_user(authorization)
        user_id = user_info.get("id")
        email = user_info.get("email") or ""
        if user_id:
            role = await _resolve_role(user_id)
    except Exception:
        pass

    # Revoke the session server-side.
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{SUPABASE_URL}/auth/v1/logout",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {token}",
                },
            )
    except Exception:
        pass  # Best-effort; local session will still be cleared by the client.

    if user_id:
        await insert_auth_audit_row(
            user_id=user_id,
            email=email,
            role=role,
            event="logout",
            action_code="E",
            outcome_code=0,
            resource_type="auth_session",
            resource_id=None,
        )

    return {"success": True}


# ─── Token refresh ───────────────────────────────────────────────────────────

@router.post("/api/v1/auth/refresh")
@limiter.limit("30/minute")
async def refresh_token(request: Request):
    """Proxy token refresh to Supabase GoTrue."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    refresh_token_val = str(body.get("refresh_token") or "")
    if not refresh_token_val:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers=_anon_headers(),
            content=json.dumps({"refresh_token": refresh_token_val}),
        )

    if resp.status_code >= 400:
        raise HTTPException(status_code=401, detail="Token refresh failed — please sign in again")

    data = resp.json()
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type", "bearer"),
        "user": data.get("user"),
    }


# ─── Signup ──────────────────────────────────────────────────────────────────

@router.post("/api/v1/auth/signup")
@limiter.limit("5/minute")
async def signup(request: Request):
    """Proxy GoTrue signup so the frontend never hits Supabase directly."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    data_meta = body.get("data") or {}

    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=_anon_headers(),
            content=json.dumps({"email": email, "password": password, "data": data_meta}),
        )

    result = resp.json() if resp.content else {}
    if not resp.ok:
        raise HTTPException(
            status_code=resp.status_code,
            detail=result.get("message") or result.get("error_description") or result.get("error") or "Signup failed",
        )

    return result


# ─── Update profile name (post-signup) ───────────────────────────────────────

@router.patch("/api/v1/auth/profile/name")
async def update_profile_name(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Update full_name in app_users (called after signup to persist the display name)."""
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    full_name = str(body.get("full_name") or "").strip()
    if len(full_name) > 80:
        raise HTTPException(status_code=400, detail="full_name must be 80 characters or fewer")

    await postgrest_patch(
        "app_users",
        f"user_id=eq.{quote(user_id, safe='')}",
        {"full_name": full_name or None},
    )
    return {"success": True}
