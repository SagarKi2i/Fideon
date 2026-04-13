import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.limiter import limiter
from app.core.supabase import (
    insert_audit_log,
    postgrest_get,
    postgrest_patch,
    service_headers,
    verify_user,
)

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_STRENGTH_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).+$")
_GENERIC_RESET_RESPONSE = {
    "success": True,
    "message": "If an account exists for this email, a password reset link has been sent.",
}


def _is_valid_password(password: str) -> bool:
    if not password or len(password) < 8 or len(password) > 72:
        return False
    return bool(_PASSWORD_STRENGTH_RE.match(password))


def _email_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


@router.post("/api/v1/auth/password-reset/request")
@limiter.limit("5/minute")
async def request_password_reset(request: Request):
    """Issue password-reset email without user enumeration."""
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    email = str(body.get("email") or "").strip().lower()
    redirect_to = str(body.get("redirect_to") or "").strip()
    if not email or not _EMAIL_RE.match(email):
        # Enumeration-safe response.
        return _GENERIC_RESET_RESPONSE

    # Optional lookup for tenant-safe auditing without exposing existence to caller.
    # Keep this best-effort: never let a lookup failure break the reset flow.
    target_user_id = None
    try:
        target_rows = await postgrest_get(
            "app_users",
            f"select=user_id&email=eq.{quote(email, safe='')}&limit=1",
        )
        target_user_id = target_rows[0].get("user_id") if target_rows else None
    except Exception:  # noqa: BLE001
        target_user_id = None

    try:
        payload = {"email": email}
        if redirect_to:
            payload["redirect_to"] = redirect_to
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/auth/v1/recover",
                headers=service_headers(),
                content=json.dumps(payload),
            )
        if resp.status_code >= 400:
            await insert_audit_log(
                request=request,
                user_id=target_user_id,
                action="reset_password_request_failed",
                resource_type="auth_user",
                resource_id=target_user_id,
                details={"email_hash": _email_hash(email), "status_code": resp.status_code},
                previous_value=None,
                new_value=None,
            )
            # Do not leak existence or delivery errors.
            return _GENERIC_RESET_RESPONSE

        await insert_audit_log(
            request=request,
            user_id=target_user_id,
            action="reset_password_requested",
            resource_type="auth_user",
            resource_id=target_user_id,
            details={"email_hash": _email_hash(email)},
            previous_value=None,
            new_value={"reset_requested": True},
        )
    except Exception:  # noqa: BLE001
        # Keep response generic to prevent enumeration.
        return _GENERIC_RESET_RESPONSE

    return _GENERIC_RESET_RESPONSE


@router.post("/api/v1/auth/password-reset/confirm")
@limiter.limit("10/minute")
async def confirm_password_reset(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Confirm password reset for the authenticated recovery session."""
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    new_password = str(body.get("password") or "")
    if not _is_valid_password(new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-72 chars and include upper, lower, number, and special character",
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{SUPABASE_URL}/auth/v1/admin/users/{quote(str(user_id), safe='')}",
                headers=service_headers(),
                content=json.dumps({"password": new_password}),
            )
        if resp.status_code >= 400:
            await insert_audit_log(
                request=request,
                user_id=user_id,
                action="reset_password_failed",
                resource_type="auth_user",
                resource_id=str(user_id),
                details={"status_code": resp.status_code},
                previous_value=None,
                new_value=None,
            )
            raise HTTPException(status_code=400, detail="Could not reset password")

        changed_at = datetime.now(timezone.utc).isoformat()
        rows = await postgrest_get(
            "app_users",
            f"select=metadata&user_id=eq.{quote(str(user_id), safe='')}&limit=1",
        )
        existing_metadata = rows[0].get("metadata") if rows and isinstance(rows[0].get("metadata"), dict) else {}
        next_metadata = {**existing_metadata, "password_updated_at": changed_at}
        await postgrest_patch(
            "app_users",
            f"user_id=eq.{quote(str(user_id), safe='')}",
            {"last_password_changed_at": changed_at, "metadata": next_metadata},
        )

        await insert_audit_log(
            request=request,
            user_id=user_id,
            action="reset_password_completed",
            resource_type="auth_user",
            resource_id=str(user_id),
            details={"password_changed": True},
            previous_value=None,
            new_value={"last_password_changed_at": changed_at},
        )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        await insert_audit_log(
            request=request,
            user_id=user_id,
            action="reset_password_failed",
            resource_type="auth_user",
            resource_id=str(user_id),
            details={"error": str(exc)[:200]},
            previous_value=None,
            new_value=None,
        )
        raise HTTPException(status_code=500, detail="Could not reset password") from exc
