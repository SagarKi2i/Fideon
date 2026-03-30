import datetime
import base64
import json
import secrets
import string
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import (
    insert_audit_log,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
    verify_user,
)

router = APIRouter()
VALID_ROLES = {"global_admin", "admin", "user", "viewer", "guest"}
ADMIN_ACCESS_REQUIRED = "Admin access required"
PASSWORD_REQUIRED = "Password is required"

# ── Roles an admin can create INSTANTLY (no approval needed) ──────────────────
ADMIN_INSTANT_ROLES = {"user", "viewer", "guest"}
# ── Roles an admin can REQUEST (needs global_admin approval) ──────────────────
ADMIN_PENDING_ROLES = {"admin"}
# ── Roles a user can REQUEST (needs admin or global_admin approval) ───────────
USER_PENDING_ROLES = {"user"}


def _generate_temp_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _get_requester_role(authorization: Optional[str]) -> tuple[dict, Optional[str], Optional[str]]:
    requester = await verify_user(authorization)
    requester_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_role = requester_roles[0].get("role") if requester_roles else None
    requester_profiles = await postgrest_get(
        "app_users", f"select=tenant_id&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_tenant_id = requester_profiles[0].get("tenant_id") if requester_profiles else None

    # For global_admin accounts, tenant_id might be NULL in app_users.
    # In that case, fall back to decoding the tenant_id claim from the JWT.
    if requester_tenant_id is None and authorization and authorization.lower().startswith("bearer "):
        try:
            token = authorization.split(" ", 1)[1]
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                # Add base64 padding if required
                payload_b64 += "=" * (-len(payload_b64) % 4)
                payload_raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
                payload = json.loads(payload_raw)
                claim_tenant_id = payload.get("tenant_id")
                if claim_tenant_id:
                    requester_tenant_id = str(claim_tenant_id)
        except Exception:
            # Best-effort fallback; don't block admin flows.
            pass
    return requester, requester_role, requester_tenant_id


def _parse_admin_create_user_body(body: dict) -> tuple[str, Optional[str], Optional[str], str, str]:
    email = body.get("email")
    password = body.get("password")
    full_name = body.get("full_name")
    role = body.get("role", "user")
    action = body.get("action", "create")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    return email, password, full_name, role, action


def _utc_now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


async def _update_password_for_existing_user(
    email: str,
    password: str,
    requester_role: Optional[str],
    requester_tenant_id: Optional[str],
) -> dict:
    users = await admin_list_users()
    user = next((u for u in users if u.get("email") == email), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if requester_role != "global_admin":
        if not requester_tenant_id:
            raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
        target_profile = await postgrest_get(
            "app_users",
            f"select=tenant_id&user_id=eq.{quote(str(user['id']), safe='')}&limit=1",
        )
        target_tenant_id = target_profile[0].get("tenant_id") if target_profile else None
        if not target_tenant_id or str(target_tenant_id) != str(requester_tenant_id):
            raise HTTPException(status_code=403, detail="Cross-tenant password update denied")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user['id']}",
            headers=service_headers(),
            content=json.dumps({"password": password}),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.text)
    return user


async def _create_auth_user(
    email: str,
    password: str,
    full_name: Optional[str],
    role: str,
    user_metadata: Optional[dict] = None,
) -> dict:
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
                        **(user_metadata or {}),
                    },
                }
            ),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=resp.text)
    body = resp.json()
    if isinstance(body, dict):
        if isinstance(body.get("user"), dict):
            return body["user"]
        # Some Supabase admin responses return user fields at the top level.
        if body.get("id"):
            return body
    return {}


async def _send_password_reset(email: str) -> None:
    """Send a password-reset email so the newly created user can set their own password."""
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            headers=service_headers(),
            content=json.dumps({"email": email}),
        )


async def _finalize_user_creation(
    request: Request,
    requester_id: str,
    email: str,
    full_name: Optional[str],
    role: str,
    tenant_id: Optional[str],
    password: Optional[str] = None,
) -> dict:
    """Create auth user + assign role + audit log. Returns user dict."""
    actual_password = password or _generate_temp_password()

    # Prepare onboarding metadata so the DB triggers can:
    # - assign app_users.tenant_id + onboarding metadata (plan/device/profile)
    # - create the initial devices row(s)
    # - create an activated_models row for a default model (we intentionally omit default_model_id)
    onboarding_metadata: dict = {}
    if tenant_id:
        try:
            tenant_id_str = str(tenant_id)

            tenants = await postgrest_get(
                "tenants",
                f"select=id,name,plan&is_active=eq.true&id=eq.{quote(tenant_id_str, safe='')}&limit=1",
            )
            tenant_row = tenants[0] if tenants else {}
            tenant_name = tenant_row.get("name")
            tenant_plan = tenant_row.get("plan")

            # Device template:
            # Prefer a device owned by the requester in this tenant; otherwise any device in the tenant.
            devices_template = await postgrest_get(
                "devices",
                (
                    "select=device_name,os_type,app_version,metadata"
                    f"&tenant_id=eq.{quote(tenant_id_str, safe='')}"
                    f"&registered_by=eq.{quote(str(requester_id), safe='')}"
                    "&limit=1"
                ),
            )
            if not devices_template:
                devices_template = await postgrest_get(
                    "devices",
                    (
                        "select=device_name,os_type,app_version,metadata"
                        f"&tenant_id=eq.{quote(tenant_id_str, safe='')}"
                        "&limit=1"
                    ),
                )

            device_name: Optional[str] = None
            device_profile: dict = {}
            if devices_template:
                d = devices_template[0] or {}
                device_name = d.get("device_name")
                md = d.get("metadata") or {}
                device_profile_from_md = md.get("device_profile") if isinstance(md, dict) else None
                if isinstance(device_profile_from_md, dict):
                    device_profile = dict(device_profile_from_md)
                # Ensure required keys exist for triggers.
                device_profile["device_name"] = device_profile.get("device_name") or device_name
                if not device_profile.get("os_name"):
                    device_profile["os_name"] = d.get("os_type") or ""
                if not device_profile.get("app_version"):
                    device_profile["app_version"] = d.get("app_version") or ""

            # Fallback if no device template exists.
            if not device_name:
                device_name = f"{tenant_name or 'TENANT'}_DEVICE"
            device_profile.setdefault("device_name", device_name)
            device_profile.setdefault("os_name", device_profile.get("os_name") or "")
            device_profile.setdefault("app_version", device_profile.get("app_version") or "")

            onboarding_metadata = {
                "tenant_name": tenant_name,
                "plan": tenant_plan,
                "device_name": device_name,
                "device_profile": device_profile,
            }
        except Exception:
            # If onboarding metadata resolution fails, still create the user.
            onboarding_metadata = {}

    user_data = await _create_auth_user(email, actual_password, full_name, role, user_metadata=onboarding_metadata)
    if not user_data.get("id"):
        raise HTTPException(status_code=500, detail="Auth user created without a valid user id")
    inherited_models_count = 0
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
        if tenant_id:
            # Trigger should already set tenant_id based on tenant_name, but keep as a best-effort fix.
            try:
                await postgrest_patch(
                    "app_users",
                    f"user_id=eq.{quote(user_data['id'], safe='')}",
                    {"tenant_id": tenant_id},
                )
            except Exception:
                pass

            # Ensure newly created devices (created by signup triggers) are in the intended tenant.
            # Devices are looked up by tenant-scoped RLS, so tenant_id must align.
            try:
                await postgrest_patch(
                    "devices",
                    f"registered_by=eq.{quote(user_data['id'], safe='')}",
                    {"tenant_id": tenant_id},
                )
            except Exception:
                pass
        # Inherit tenant model access for the newly created user.
        # We copy distinct model assignments that already exist within the tenant.
        if tenant_id:
            try:
                existing_models = await postgrest_get(
                    "activated_models",
                    f"select=model_id&user_id=eq.{quote(str(user_data['id']), safe='')}",
                )
                existing_model_ids = {str(r.get("model_id")) for r in (existing_models or []) if r.get("model_id")}

                tenant_users = await postgrest_get(
                    "app_users",
                    f"select=user_id&tenant_id=eq.{quote(str(tenant_id), safe='')}",
                )
                tenant_user_ids = [str(row.get("user_id")) for row in tenant_users if row.get("user_id")]
                if tenant_user_ids:
                    encoded_user_ids = ",".join(quote(uid, safe="") for uid in tenant_user_ids)
                    tenant_models = await postgrest_get(
                        "activated_models",
                        f"select=model_id,model_name,domain&user_id=in.({encoded_user_ids})",
                    )
                    seen_model_ids: set[str] = set()
                    for row in tenant_models:
                        model_id = str(row.get("model_id") or "").strip()
                        model_name = str(row.get("model_name") or "").strip()
                        domain = str(row.get("domain") or "").strip()
                        if not model_id or not model_name or not domain:
                            continue
                        if model_id in seen_model_ids:
                            continue
                        if model_id in existing_model_ids:
                            seen_model_ids.add(model_id)
                            continue
                        seen_model_ids.add(model_id)
                        try:
                            await postgrest_insert(
                                "activated_models",
                                {
                                    "user_id": user_data["id"],
                                    "model_id": model_id,
                                    "model_name": model_name,
                                    "domain": domain,
                                },
                            )
                            existing_model_ids.add(model_id)
                            inherited_models_count += 1
                        except Exception:
                            # Best-effort: don't block creation if a single model insert fails.
                            continue
            except Exception:
                # Best effort: user creation must not fail if model inheritance fails.
                pass
        # If no password was supplied, send a reset link so user can self-set
        if not password:
            try:
                await _send_password_reset(email)
            except Exception:
                pass
        await insert_audit_log(
            request=request,
            user_id=requester_id,
            action="create_user",
            resource_type="user",
            resource_id=user_data["id"],
            details={"role": role},
            previous_value=None,
            new_value={"role": role},
        )
    user_data["inherited_models_count"] = inherited_models_count
    return user_data


async def _handle_update_password_action(
    request: Request,
    requester: dict,
    requester_role: Optional[str],
    requester_tenant_id: Optional[str],
    email: str,
    password: Optional[str],
) -> dict:
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)
    if not password:
        raise HTTPException(status_code=400, detail=PASSWORD_REQUIRED)
    user = await _update_password_for_existing_user(
        email=email,
        password=password,
        requester_role=requester_role,
        requester_tenant_id=requester_tenant_id,
    )
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


async def _handle_global_admin_create(
    request: Request,
    requester: dict,
    email: str,
    full_name: Optional[str],
    role: str,
    tenant_id: Optional[str],
    password: Optional[str],
) -> dict:
    if not password:
        raise HTTPException(status_code=400, detail=PASSWORD_REQUIRED)
    user_data = await _finalize_user_creation(
        request, requester["id"], email, full_name, role, tenant_id, password
    )
    return {"success": True, "pending": False,
            "user": {"id": user_data.get("id"), "email": user_data.get("email")},
            "inherited_models_count": int(user_data.get("inherited_models_count") or 0)}


async def _queue_user_creation_request(
    request: Request,
    requester: dict,
    requester_role: str,
    requester_tenant_id: Optional[str],
    email: str,
    full_name: Optional[str],
    role: str,
) -> None:
    await postgrest_insert(
        "user_creation_requests",
        {
            "requested_by": requester["id"],
            "requester_role": requester_role,
            "tenant_id": requester_tenant_id,
            "email": email,
            "full_name": full_name,
            "requested_role": role,
            "status": "pending",
        },
    )
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="request_create_user",
        resource_type="user_creation_request",
        resource_id=None,
        details={"role": role, "email": email},
        previous_value=None,
        new_value={"status": "pending", "role": role},
    )


async def _handle_admin_create(
    request: Request,
    requester: dict,
    email: str,
    password: Optional[str],
    full_name: Optional[str],
    role: str,
    requester_tenant_id: Optional[str],
) -> dict:
    if role in ADMIN_INSTANT_ROLES:
        if not password:
            raise HTTPException(status_code=400, detail=PASSWORD_REQUIRED)
        user_data = await _finalize_user_creation(
            request, requester["id"], email, full_name, role, requester_tenant_id, password
        )
        return {"success": True, "pending": False,
                "user": {"id": user_data.get("id"), "email": user_data.get("email")},
                "inherited_models_count": int(user_data.get("inherited_models_count") or 0)}

    if role in ADMIN_PENDING_ROLES:
        await _queue_user_creation_request(
            request, requester, "admin", requester_tenant_id, email, full_name, role
        )
        return {
            "success": True,
            "pending": True,
            "message": f"Request to create an admin user ({email}) has been submitted for global admin approval.",
        }

    raise HTTPException(status_code=403, detail="Admins cannot create this role")


async def _handle_user_create(
    request: Request,
    requester: dict,
    requester_tenant_id: Optional[str],
    email: str,
    full_name: Optional[str],
    role: str,
) -> dict:
    if role not in USER_PENDING_ROLES:
        raise HTTPException(status_code=403, detail="Users can only request creation of 'user' role accounts")
    await _queue_user_creation_request(
        request, requester, "user", requester_tenant_id, email, full_name, role
    )
    return {
        "success": True,
        "pending": True,
        "message": f"Request to create user ({email}) has been submitted for admin approval.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# LIST USERS
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/api/list-users")
async def list_users(authorization: Optional[str] = Header(default=None)):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    rows = await postgrest_get(
        "app_users",
        (
            "select=user_id,email,created_at,tenant_id"
            f"&tenant_id=eq.{quote(requester_tenant_id, safe='')}"
            "&order=created_at.desc"
        ),
    )
    tenant_name_map: dict[str, str] = {}
    tenant_rows = await postgrest_get(
        "tenants",
        f"select=id,name&id=eq.{quote(requester_tenant_id, safe='')}&limit=1",
    )
    if tenant_rows:
        tenant_row = tenant_rows[0]
        tenant_id_value = str(tenant_row.get("id") or requester_tenant_id)
        tenant_name_map[tenant_id_value] = str(tenant_row.get("name") or "")

    user_ids = [str(row.get("user_id")) for row in rows if row.get("user_id")]
    role_map: dict[str, str] = {}
    if user_ids:
        id_list = ",".join(quote(uid, safe="") for uid in user_ids)
        role_rows = await postgrest_get(
            "user_roles",
            f"select=user_id,role&user_id=in.({id_list})",
        )
        role_map = {str(r.get("user_id")): str(r.get("role")) for r in role_rows}
    out = []
    for row in rows:
        role_value = role_map.get(str(row.get("user_id")), "user")
        out.append(
            {
                "id": row.get("user_id"),
                "email": row.get("email"),
                "role": role_value,
                "created_at": row.get("created_at"),
                "tenant_id": row.get("tenant_id"),
                "tenant_name": tenant_name_map.get(str(row.get("tenant_id") or ""), ""),
            }
        )
    return {"users": out}


@router.get("/api/admin/dashboard-stats")
async def admin_dashboard_stats(authorization: Optional[str] = Header(default=None)):
    _, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    def _iso_utc(dt: datetime.datetime) -> str:
        # Supabase / PostgREST handles timestamptz in ISO-8601; keep UTC Z suffix.
        return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    now = datetime.datetime.now(datetime.timezone.utc)
    day_ago = now - datetime.timedelta(days=1)
    two_days_ago = now - datetime.timedelta(days=2)
    week_ago = now - datetime.timedelta(days=7)
    thirty_days_from_now = now + datetime.timedelta(days=30)

    tenant_id_str = str(requester_tenant_id)
    tenant_id_q = quote(tenant_id_str, safe="")

    # Tenant user ids (including admins), then exclude admin/global_admin for dashboard metrics.
    tenant_users = await postgrest_get("app_users", f"select=user_id&tenant_id=eq.{tenant_id_q}")
    tenant_user_ids = [str(row.get("user_id")) for row in (tenant_users or []) if row.get("user_id")]

    if not tenant_user_ids:
        return {
            "total_devices": 0,
            "online_devices": 0,
            "offline_devices": 0,
            "pending_approvals": 0,
            "expiring_soon": 0,
            "sync_failures": 0,
            "total_models_assigned": 0,
            "usage_today": 0,
            "usage_yesterday": 0,
            "devices_created_this_week": 0,
        }

    encoded_tenant_user_ids = ",".join(quote(uid, safe="") for uid in tenant_user_ids)
    admin_role_rows = await postgrest_get(
        "user_roles",
        f"select=user_id,role&user_id=in.({encoded_tenant_user_ids})&role=in.(admin,global_admin)",
    )
    admin_user_ids = {str(r.get("user_id")) for r in (admin_role_rows or []) if r.get("user_id")}
    non_admin_user_ids = [uid for uid in tenant_user_ids if uid not in admin_user_ids]

    # Devices: include only devices registered by non-admin users (or unknown/NULL registrant).
    device_rows = await postgrest_get(
        "devices",
        f"select=id,status,registered_by,registered_at&tenant_id=eq.{tenant_id_q}",
    )
    included_device_rows: list[dict] = []
    non_admin_user_id_set = set(non_admin_user_ids)
    for d in device_rows or []:
        registered_by = d.get("registered_by")
        if registered_by is None:
            included_device_rows.append(d)
            continue
        if str(registered_by) in non_admin_user_id_set:
            included_device_rows.append(d)

    total_devices = len(included_device_rows)
    online_devices = sum(1 for d in included_device_rows if d.get("status") == "online")
    offline_devices = sum(1 for d in included_device_rows if d.get("status") == "offline")
    included_device_ids = [str(d.get("id")) for d in included_device_rows if d.get("id")]

    devices_created_this_week = 0
    for d in included_device_rows:
        ra = d.get("registered_at")
        if not isinstance(ra, str):
            continue
        try:
            ra_dt = datetime.datetime.fromisoformat(ra.replace("Z", "+00:00"))
            ra_dt = ra_dt.astimezone(datetime.timezone.utc)
            if ra_dt >= week_ago:
                devices_created_this_week += 1
        except Exception:
            # Best effort: if timestamp parsing fails, ignore that device.
            continue

    # Pending approvals: pod activation requests for tenant non-admin users only.
    pending_approvals = 0
    if non_admin_user_ids:
        encoded_non_admin_user_ids = ",".join(quote(uid, safe="") for uid in non_admin_user_ids)
        par_rows = await postgrest_get(
            "pod_activation_requests",
            (
                f"select=id"
                f"&tenant_id=eq.{tenant_id_q}"
                f"&status=eq.pending"
                f"&user_id=in.({encoded_non_admin_user_ids})"
            ),
        )
        pending_approvals = len(par_rows or [])

    # Expiring soon: device licenses for devices owned by tenant non-admin users only.
    expiring_soon = 0
    if included_device_ids:
        encoded_device_ids = ",".join(quote(did, safe="") for did in included_device_ids)
        now_iso = _iso_utc(now)
        thirty_iso = _iso_utc(thirty_days_from_now)
        license_rows = await postgrest_get(
            "device_licenses",
            (
                f"select=id"
                f"&device_id=in.({encoded_device_ids})"
                f"&expires_at=not.is.null"
                f"&expires_at=gte.{quote(now_iso, safe='')}"
                f"&expires_at=lte.{quote(thirty_iso, safe='')}"
            ),
        )
        expiring_soon = len(license_rows or [])

    # Sync failures: failed sync logs in last 24h for non-admin owned devices.
    sync_failures = 0
    if included_device_ids:
        encoded_device_ids = ",".join(quote(did, safe="") for did in included_device_ids)
        day_ago_iso = _iso_utc(day_ago)
        dsl_rows = await postgrest_get(
            "device_sync_logs",
            (
                f"select=id"
                f"&tenant_id=eq.{tenant_id_q}"
                f"&status=eq.failed"
                f"&created_at=gte.{quote(day_ago_iso, safe='')}"
                f"&device_id=in.({encoded_device_ids})"
            ),
        )
        sync_failures = len(dsl_rows or [])

    # Models assigned: activated models for tenant non-admin users.
    total_models_assigned = 0
    if non_admin_user_ids:
        encoded_non_admin_user_ids = ",".join(quote(uid, safe="") for uid in non_admin_user_ids)
        model_rows = await postgrest_get(
            "activated_models",
            f"select=id&user_id=in.({encoded_non_admin_user_ids})",
        )
        total_models_assigned = len(model_rows or [])

    # Usage today / yesterday: chat messages from conversations owned by tenant non-admin users.
    usage_today = 0
    usage_yesterday = 0
    if non_admin_user_ids:
        encoded_non_admin_user_ids = ",".join(quote(uid, safe="") for uid in non_admin_user_ids)
        conv_rows = await postgrest_get(
            "chat_conversations",
            f"select=id&user_id=in.({encoded_non_admin_user_ids})",
        )
        conversation_ids = [str(r.get("id")) for r in (conv_rows or []) if r.get("id")]

        if conversation_ids:
            encoded_conversation_ids = ",".join(quote(cid, safe="") for cid in conversation_ids)
            day_ago_iso = _iso_utc(day_ago)
            two_days_ago_iso = _iso_utc(two_days_ago)

            usage_today_rows = await postgrest_get(
                "chat_messages",
                (
                    f"select=id"
                    f"&conversation_id=in.({encoded_conversation_ids})"
                    f"&created_at=gte.{quote(day_ago_iso, safe='')}"
                ),
            )
            usage_today = len(usage_today_rows or [])

            usage_yesterday_rows = await postgrest_get(
                "chat_messages",
                (
                    f"select=id"
                    f"&conversation_id=in.({encoded_conversation_ids})"
                    f"&created_at=gte.{quote(two_days_ago_iso, safe='')}"
                    f"&created_at=lt.{quote(day_ago_iso, safe='')}"
                ),
            )
            usage_yesterday = len(usage_yesterday_rows or [])

    return {
        "total_devices": total_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "pending_approvals": pending_approvals,
        "expiring_soon": expiring_soon,
        "sync_failures": sync_failures,
        "total_models_assigned": total_models_assigned,
        "usage_today": usage_today,
        "usage_yesterday": usage_yesterday,
        "devices_created_this_week": devices_created_this_week,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CREATE USER  (with approval-workflow logic)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/api/admin-create-user")
async def admin_create_user(request: Request, authorization: Optional[str] = Header(default=None)):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)

    body = await request.json()
    email, password, full_name, role, action = _parse_admin_create_user_body(body)

    # ── Password-update action (admin/global_admin only) ──────────────────────
    if action == "update_password":
        return await _handle_update_password_action(
            request, requester, requester_role, requester_tenant_id, email, password
        )

    # ── GLOBAL ADMIN: create any role instantly ───────────────────────────────
    if requester_role == "global_admin":
        return await _handle_global_admin_create(
            request, requester, email, full_name, role, requester_tenant_id, password
        )

    # ── ADMIN: instant for user/viewer/guest; pending for admin ───────────────
    if requester_role == "admin":
        return await _handle_admin_create(
            request, requester, email, password, full_name, role, requester_tenant_id
        )

    # ── USER: can request creation of another user (pending approval) ─────────
    if requester_role == "user":
        return await _handle_user_create(
            request, requester, requester_tenant_id, email, full_name, role
        )

    # viewer and guest cannot create or request any users
    raise HTTPException(status_code=403, detail=f"Role '{requester_role}' is not permitted to create or request user accounts")


# ─────────────────────────────────────────────────────────────────────────────
# SET USER ROLE (global_admin only)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/api/admin-set-user-role")
async def admin_set_user_role(request: Request, authorization: Optional[str] = Header(default=None)):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role != "global_admin":
        raise HTTPException(status_code=403, detail="Global admin access required")
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    body = await request.json()
    user_id = body.get("user_id")
    role = body.get("role")
    if not user_id or role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Valid user_id and role are required")
    target_profiles = await postgrest_get(
        "app_users",
        f"select=tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    target_tenant_id = target_profiles[0].get("tenant_id") if target_profiles else None
    if not target_tenant_id or str(target_tenant_id) != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant role change denied")

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


# ─────────────────────────────────────────────────────────────────────────────
# LIST USER CREATION REQUESTS
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/api/user-creation-requests")
async def list_user_creation_requests(authorization: Optional[str] = Header(default=None)):
    _, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    # Tenant-only queue. Admin sees user requests; global_admin sees tenant queue.
    base = (
        "select=*"
        f"&tenant_id=eq.{quote(requester_tenant_id, safe='')}"
        "&status=eq.pending"
        "&order=created_at.asc"
    )
    if requester_role == "admin":
        base += "&requester_role=eq.user"
    rows = await postgrest_get("user_creation_requests", base)

    return {"requests": rows or []}


# ─────────────────────────────────────────────────────────────────────────────
# MY USER CREATION REQUESTS (for regular users to track their submitted requests)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/api/my-user-creation-requests")
async def my_user_creation_requests(authorization: Optional[str] = Header(default=None)):
    requester, _, requester_tenant_id = await _get_requester_role(authorization)
    rows = await postgrest_get(
        "user_creation_requests",
        (
            "select=*"
            f"&requested_by=eq.{quote(requester['id'], safe='')}"
            f"&tenant_id=eq.{quote(str(requester_tenant_id or ''), safe='')}"
            "&order=created_at.desc&limit=20"
        ),
    )
    return {"requests": rows or []}


# ─────────────────────────────────────────────────────────────────────────────
# APPROVE USER CREATION REQUEST
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/api/user-creation-requests/{request_id}/approve")
async def approve_user_creation_request(
    request_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)

    # Fetch the pending request
    rows = await postgrest_get(
        "user_creation_requests",
        (
            "select=*"
            f"&id=eq.{quote(request_id, safe='')}"
            "&status=eq.pending"
            f"&tenant_id=eq.{quote(str(requester_tenant_id or ''), safe='')}"
            "&limit=1"
        ),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pending request not found")

    ucr = rows[0]

    # Enforce approval authority:
    # - admin→admin requests: only global_admin can approve
    # - user→user requests: admin OR global_admin can approve
    if ucr["requester_role"] == "admin" and requester_role != "global_admin":
        raise HTTPException(
            status_code=403,
            detail="Only a global admin can approve admin-role creation requests",
        )

    # Create the user (temp password + password-reset email)
    user_data = await _finalize_user_creation(
        request,
        requester["id"],
        ucr["email"],
        ucr.get("full_name"),
        ucr["requested_role"],
        requester_tenant_id,
        password=None,   # temp password generated; reset email sent automatically
    )

    # Mark request as approved
    await postgrest_patch(
        "user_creation_requests",
        f"id=eq.{quote(request_id, safe='')}",
        {
            "status": "approved",
            "reviewed_by": requester["id"],
            "reviewed_at": _utc_now_z(),
        },
    )

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="approve_user_creation_request",
        resource_type="user_creation_request",
        resource_id=request_id,
        details={"email": ucr["email"], "role": ucr["requested_role"]},
        previous_value={"status": "pending"},
        new_value={"status": "approved"},
    )

    return {
        "success": True,
        "message": f"User {ucr['email']} created with role '{ucr['requested_role']}'. A password-reset email has been sent.",
        "user": {"id": user_data.get("id"), "email": user_data.get("email")},
        "inherited_models_count": int(user_data.get("inherited_models_count") or 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# REJECT USER CREATION REQUEST
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/api/user-creation-requests/{request_id}/reject")
async def reject_user_creation_request(
    request_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    if requester_role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail=ADMIN_ACCESS_REQUIRED)

    rows = await postgrest_get(
        "user_creation_requests",
        (
            "select=*"
            f"&id=eq.{quote(request_id, safe='')}"
            "&status=eq.pending"
            f"&tenant_id=eq.{quote(str(requester_tenant_id or ''), safe='')}"
            "&limit=1"
        ),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pending request not found")

    ucr = rows[0]

    # Same authority rule as approval
    if ucr["requester_role"] == "admin" and requester_role != "global_admin":
        raise HTTPException(
            status_code=403,
            detail="Only a global admin can reject admin-role creation requests",
        )

    body = await request.json()
    rejection_reason = body.get("reason", "")

    await postgrest_patch(
        "user_creation_requests",
        f"id=eq.{quote(request_id, safe='')}",
        {
            "status": "rejected",
            "reviewed_by": requester["id"],
            "reviewed_at": _utc_now_z(),
            "rejection_reason": rejection_reason,
        },
    )

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="reject_user_creation_request",
        resource_type="user_creation_request",
        resource_id=request_id,
        details={"email": ucr["email"], "role": ucr["requested_role"], "reason": rejection_reason},
        previous_value={"status": "pending"},
        new_value={"status": "rejected"},
    )

    return {"success": True, "message": f"Request for {ucr['email']} has been rejected."}
