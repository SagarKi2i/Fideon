"""
Notifications — user_notifications CRUD + realtime backlog + user label lookup.
All DB access goes through the service-role PostgREST client; the frontend never
hits Supabase directly.
"""
import datetime as dt
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import (
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    verify_admin,
    verify_user,
)

router = APIRouter()


async def _user_id(authorization: Optional[str]) -> str:
    user = await verify_user(authorization)
    uid = user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return uid


async def _get_role(user_id: str) -> str:
    try:
        rows = await postgrest_get(
            "user_roles",
            f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1",
        )
        return rows[0].get("role", "user") if rows else "user"
    except Exception:
        return "user"


# ─── List notifications ───────────────────────────────────────────────────────

@router.get("/api/v1/notifications")
async def list_notifications(authorization: Optional[str] = Header(default=None)):
    uid = await _user_id(authorization)
    rows = await postgrest_get(
        "user_notifications",
        (
            "select=id,table_name,event_type,message,target_path,created_at,read_at,source_fingerprint"
            f"&user_id=eq.{quote(uid, safe='')}"
            "&order=created_at.desc&limit=50"
        ),
    )
    return {"notifications": rows}


# ─── Create notification (used by realtime handlers on the client) ────────────

@router.post("/api/v1/notifications")
async def create_notification(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _user_id(authorization)

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    target_user_id = str(body.get("user_id") or uid)

    # Only allow writing for yourself unless caller is admin.
    if target_user_id != uid:
        await verify_admin(authorization)

    table_name = str(body.get("table_name") or "")
    message = str(body.get("message") or "")
    event_type = str(body.get("event_type") or "INSERT")
    target_path = body.get("target_path")
    fingerprint = str(body.get("source_fingerprint") or "") or None

    if not table_name or not message:
        raise HTTPException(status_code=400, detail="table_name and message are required")

    # Dedup: skip if same fingerprint seen in last 20 s.
    if fingerprint:
        dedup_since = (datetime.now(timezone.utc) - dt.timedelta(seconds=20)).isoformat()
        existing = await postgrest_get(
            "user_notifications",
            (
                f"select=id&user_id=eq.{quote(target_user_id, safe='')}"
                f"&source_fingerprint=eq.{quote(fingerprint, safe='')}"
                f"&created_at=gte.{quote(dedup_since, safe='')}&limit=1"
            ),
        )
        if existing:
            return {"success": True, "deduplicated": True}

    await postgrest_insert(
        "user_notifications",
        {
            "user_id": target_user_id,
            "table_name": table_name,
            "event_type": event_type,
            "message": message,
            "target_path": target_path,
            "source_fingerprint": fingerprint,
        },
    )
    return {"success": True}


# ─── Mark all read ────────────────────────────────────────────────────────────

@router.post("/api/v1/notifications/mark-all-read")
async def mark_all_read(authorization: Optional[str] = Header(default=None)):
    uid = await _user_id(authorization)
    now = datetime.now(timezone.utc).isoformat()
    await postgrest_patch(
        "user_notifications",
        f"user_id=eq.{quote(uid, safe='')}&read_at=is.null",
        {"read_at": now},
    )
    return {"success": True}


# ─── Delete all ───────────────────────────────────────────────────────────────

@router.delete("/api/v1/notifications")
async def clear_all_notifications(authorization: Optional[str] = Header(default=None)):
    uid = await _user_id(authorization)
    await postgrest_delete(
        "user_notifications",
        f"user_id=eq.{quote(uid, safe='')}",
    )
    return {"success": True}


# ─── Mark one read ────────────────────────────────────────────────────────────

@router.patch("/api/v1/notifications/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: str,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _user_id(authorization)
    now = datetime.now(timezone.utc).isoformat()
    await postgrest_patch(
        "user_notifications",
        (
            f"id=eq.{quote(notification_id, safe='')}"
            f"&user_id=eq.{quote(uid, safe='')}"
            "&read_at=is.null"
        ),
        {"read_at": now},
    )
    return {"success": True}


# ─── Backlog (replaces direct Supabase queries in useGlobalRealtimeSubscriptions) ──

@router.get("/api/v1/notifications/backlog")
async def get_notification_backlog(authorization: Optional[str] = Header(default=None)):
    """Return recent pod-request / decision-review rows for backlog replay.

    Admins get all recent records (last 24 h).
    Regular users get only their own approved/rejected outcomes.
    """
    uid = await _user_id(authorization)
    role = await _get_role(uid)
    is_admin = role in ("admin", "global_admin")

    recent_iso = (datetime.now(timezone.utc) - dt.timedelta(hours=24)).isoformat()

    if is_admin:
        pods = await postgrest_get(
            "pod_activation_requests",
            (
                "select=id,user_id,model_name,status,requested_at"
                f"&requested_at=gte.{quote(recent_iso, safe='')}"
                "&order=requested_at.desc&limit=20"
            ),
        )
        reviews = await postgrest_get(
            "decision_reviews",
            (
                "select=id,user_id,title,status,created_at"
                f"&created_at=gte.{quote(recent_iso, safe='')}"
                "&order=created_at.desc&limit=20"
            ),
        )
    else:
        pods = await postgrest_get(
            "pod_activation_requests",
            (
                "select=id,user_id,model_name,status,reviewed_at"
                f"&user_id=eq.{quote(uid, safe='')}"
                "&status=in.(approved,rejected)"
                "&order=reviewed_at.desc&limit=20"
            ),
        )
        reviews = await postgrest_get(
            "decision_reviews",
            (
                "select=id,user_id,title,status,reviewed_at"
                f"&user_id=eq.{quote(uid, safe='')}"
                "&status=in.(approved,rejected)"
                "&order=reviewed_at.desc&limit=20"
            ),
        )

    return {
        "is_admin": is_admin,
        "user_id": uid,
        "role": role,
        "pods": pods,
        "reviews": reviews,
    }


# ─── User label (replaces direct app_users query for resolveRequesterLabel) ───

@router.get("/api/v1/users/{target_user_id}/label")
async def get_user_label(
    target_user_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Return display label (full_name or email) for a user. Requires admin role."""
    await verify_admin(authorization)
    rows = await postgrest_get(
        "app_users",
        f"select=full_name,email&user_id=eq.{quote(target_user_id, safe='')}&limit=1",
    )
    if not rows:
        return {"label": f"user {target_user_id[:8]}"}
    row = rows[0]
    full_name = (row.get("full_name") or "").strip()
    email = (row.get("email") or "").strip()
    label = full_name or email or f"user {target_user_id[:8]}"
    return {"label": label}
