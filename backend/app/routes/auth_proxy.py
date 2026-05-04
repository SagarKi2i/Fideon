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

from app.core.config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
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
_PASSWORD_STRENGTH_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).+$")
_PASSWORD_MIN = 8
_PASSWORD_MAX = 72


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
    if len(password) < _PASSWORD_MIN or len(password) > _PASSWORD_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be {_PASSWORD_MIN}–{_PASSWORD_MAX} characters.",
        )
    if not _PASSWORD_STRENGTH_RE.match(password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special character.",
        )

    # ── Seat-limit pre-flight check (before calling GoTrue) ──────────────────
    # Enforcing here avoids leaving an orphaned auth.users row when the tenant
    # is already at its seat limit — the DB trigger is the final safety net.
    tenant_name_meta = str(data_meta.get("tenant_name") or "").strip()
    if tenant_name_meta:
        try:
            tenant_rows = await postgrest_get(
                "tenants",
                f"select=id,max_users&is_active=eq.true&name=eq.{quote(tenant_name_meta, safe='')}&limit=1",
            )
            if tenant_rows:
                t_row = tenant_rows[0]
                t_max_users = t_row.get("max_users")
                if t_max_users is not None:
                    t_id = str(t_row.get("id") or "")
                    if t_id:
                        seat_rows = await postgrest_get(
                            "app_users",
                            f"select=user_id&tenant_id=eq.{quote(t_id, safe='')}&status=neq.deleted",
                        )
                        current_count = len(seat_rows or [])
                        if current_count >= int(t_max_users):
                            raise HTTPException(
                                status_code=422,
                                detail=(
                                    f"FIDEON_OS_LIMIT:SEATS Seat limit reached ({current_count}/{t_max_users}). "
                                    "Upgrade your plan to add more users."
                                ),
                            )
        except HTTPException:
            raise
        except Exception:
            pass  # Non-blocking: if lookup fails, let the DB trigger enforce it

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=_anon_headers(),
            content=json.dumps({"email": email, "password": password, "data": data_meta}),
        )

    result = resp.json() if resp.content else {}
    if not resp.ok:
        # GoTrue uses different keys depending on version: "msg", "message", "error_description", "error".
        raw_msg: str = (
            result.get("msg")
            or result.get("message")
            or result.get("error_description")
            or result.get("error")
            or ""
        )
        raw_lower = raw_msg.lower()

        # DB trigger failures surface as GoTrue 500 with generic "Database error saving new user".
        # Map the known structured errors to readable messages.
        if resp.status_code == 500:
            if "fideon_os_limit:seats" in raw_lower or "seat limit reached" in raw_lower:
                raise HTTPException(status_code=422, detail="FIDEON_OS_LIMIT:SEATS This tenant has reached its user seat limit. Contact your administrator to upgrade the plan.")
            if "fideon_os_limit:packs" in raw_lower or "pack limit reached" in raw_lower:
                raise HTTPException(status_code=422, detail="FIDEON_OS_LIMIT:PACKS Agent pack limit reached for this tenant. Select fewer packs or upgrade the plan.")

            # GoTrue sometimes commits the auth.users row but fails during post-commit
            # token issuance (e.g. custom access token hook error). In that case the
            # user IS created but the signup call returns 500. Attempt a silent login to
            # recover a valid session — if it succeeds the user was created successfully.
            try:
                async with httpx.AsyncClient(timeout=5) as recovery_client:
                    login_resp = await recovery_client.post(
                        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                        headers=_anon_headers(),
                        content=json.dumps({"email": email, "password": password}),
                    )
                if login_resp.status_code == 200:
                    return login_resp.json()
            except Exception:
                pass  # Recovery login failed; try DB presence check next.

            # Recovery login failed — check if the user row was actually committed.
            # Handles cases where a custom access token hook fails on both signup
            # and login, but the app_users record IS present (trigger succeeded).
            try:
                existing = await postgrest_get(
                    "app_users",
                    f"select=user_id,status&email=eq.{quote(email, safe='')}&limit=1",
                )
                if existing:
                    return {"created_needs_verification": True, "email": email}
            except Exception:
                pass

            # Final fallback: check auth.users directly via the GoTrue admin API.
            # Catches the case where auth.users was committed but the app_users
            # trigger failed, leaving no row in app_users for the check above.
            try:
                async with httpx.AsyncClient(timeout=5) as admin_client:
                    admin_resp = await admin_client.get(
                        f"{SUPABASE_URL}/auth/v1/admin/users",
                        headers={
                            "apikey": SUPABASE_SERVICE_ROLE_KEY,
                            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        },
                        params={"email": email, "per_page": "1"},
                    )
                if admin_resp.status_code == 200:
                    users_list = (admin_resp.json() or {}).get("users") or []
                    if any(str(u.get("email") or "").lower() == email for u in users_list):
                        return {"created_needs_verification": True, "email": email}
            except Exception:
                pass

            raise HTTPException(status_code=500, detail=raw_msg or "Signup failed due to an internal error. Please try again.")

        # GoTrue 422 / 400 for duplicate email — normalise to a clear message.
        if resp.status_code in (400, 422):
            if any(k in raw_lower for k in ("already registered", "already been registered", "already exists", "email_exists", "user already")):
                raise HTTPException(status_code=409, detail="This email is already registered. Please sign in or use a different email address.")

        raise HTTPException(status_code=resp.status_code, detail=raw_msg or "Signup failed")

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
