import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import SUPABASE_URL
from app.core.supabase import (
    get_user_context,
    insert_audit_log,
    insert_auth_audit_row,
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    service_headers,
    verify_user,
)
from app.services.tenant_activation_limits import assert_tenant_may_add_distinct_model
from app.services.webhook_engine import WEBHOOK_EVENT_MODEL_DEPLOYED, try_emit_webhook_event

router = APIRouter()
VALID_STATUSES = {"pending", "approved", "rejected"}


async def _sync_model_to_user_devices(
    user_id: str, model_id: str, model_name: str, domain: str, allocated_by: str
) -> None:
    """
    After a model is allocated to a user, auto-insert device_models rows for all
    active devices registered by that user so Device Setup shows the same list as
    My Models. Non-blocking — errors are swallowed so allocation always succeeds.
    """
    try:
        devices = await postgrest_get(
            "devices",
            f"select=id&registered_by=eq.{quote(user_id, safe='')}&is_active=eq.true",
        )
        if not devices:
            return

        rows = [
            {
                "device_id": str(d["id"]),
                "model_id": model_id,
                "model_name": model_name,
                "domain": domain,
                "ollama_model_name": f"{model_id}:latest",
                "allocated_by": allocated_by,
            }
            for d in devices
            if d.get("id")
        ]
        if not rows:
            return

        headers = service_headers()
        # ignore-duplicates: if the admin already added this model to the device manually, skip
        headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/device_models",
                headers=headers,
                content=json.dumps(rows),
            )

        # Notify each device about the new model (best-effort)
        try:
            from app.services.device_sync_orchestrator import trigger_device_sync
            await asyncio.gather(
                *[trigger_device_sync(str(d["id"]), model_ids=[model_id]) for d in devices if d.get("id")],
                return_exceptions=True,
            )
        except Exception:
            pass
    except Exception:
        pass


async def _remove_model_from_user_devices(user_id: str, model_id: str) -> None:
    """
    After a model is removed from a user's activated_models, also remove the
    corresponding device_models rows for all devices registered by that user.
    Non-blocking.
    """
    try:
        devices = await postgrest_get(
            "devices",
            f"select=id&registered_by=eq.{quote(user_id, safe='')}&is_active=eq.true",
        )
        if not devices:
            return
        device_ids = [str(d["id"]) for d in devices if d.get("id")]
        if not device_ids:
            return
        encoded_ids = ",".join(quote(did, safe="") for did in device_ids)
        await postgrest_delete(
            "device_models",
            f"device_id=in.({encoded_ids})&model_id=eq.{quote(model_id, safe='')}",
        )
    except Exception:
        pass


VALID_DOMAINS = {"insurance", "healthcare", "banking", "legal", "travel"}


async def _get_requester_role(authorization: Optional[str]) -> tuple[dict, Optional[str]]:
    requester = await verify_user(authorization)
    requester_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_role = requester_roles[0].get("role") if requester_roles else None
    return requester, requester_role


def _require_admin(role: Optional[str]) -> None:
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")


def _is_missing_tenant_column(exc: HTTPException) -> bool:
    detail = str(exc.detail).lower()
    return "tenant_id" in detail and "pod_activation_requests" in detail


async def _require_same_tenant_user(user_id: str, requester_tenant_id: str) -> None:
    rows = await postgrest_get(
        "app_users",
        f"select=tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    target_tenant_id = rows[0].get("tenant_id") if rows else None
    if not target_tenant_id or str(target_tenant_id) != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


@router.get("/api/pod-activation/my-activations")
async def list_my_activations(authorization: Optional[str] = Header(default=None)):
    requester = await verify_user(authorization)
    rows = await postgrest_get(
        "activated_models",
        f"select=model_id&user_id=eq.{quote(requester['id'], safe='')}",
    )
    return {"model_ids": [r.get("model_id") for r in rows if r.get("model_id")]}


@router.get("/api/pod-activation/my-requests")
async def list_my_requests(
    status: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    context = await get_user_context(authorization)
    requester = context.get("user") or {}
    requester_tenant_id = context.get("tenant_id")
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    query = (
        "select=*"
        f"&user_id=eq.{quote(requester['id'], safe='')}"
        f"&tenant_id=eq.{quote(str(requester_tenant_id), safe='')}"
        "&order=requested_at.desc"
    )
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"
    try:
        rows = await postgrest_get("pod_activation_requests", query)
    except HTTPException as exc:
        if not _is_missing_tenant_column(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Tenant isolation migration required for pod activation requests",
        ) from exc
    return {"requests": rows}


@router.post("/api/pod-activation/request")
async def create_activation_request(request: Request, authorization: Optional[str] = Header(default=None)):
    context = await get_user_context(authorization)
    requester = context.get("user") or {}
    requester_tenant_id = context.get("tenant_id")
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
    body = await request.json()
    model_id = (body.get("model_id") or "").strip()
    model_name = (body.get("model_name") or "").strip()
    domain = (body.get("domain") or "").strip()

    if not model_id or not model_name or domain not in VALID_DOMAINS:
        raise HTTPException(status_code=400, detail="model_id, model_name and valid domain are required")

    await assert_tenant_may_add_distinct_model(str(requester_tenant_id), model_id)

    try:
        created = await postgrest_insert(
            "pod_activation_requests",
            {
                "user_id": requester["id"],
                "model_id": model_id,
                "model_name": model_name,
                "domain": domain,
                "status": "pending",
                "tenant_id": requester_tenant_id,
            },
        )
    except HTTPException as exc:
        if _is_missing_tenant_column(exc):
            raise HTTPException(
                status_code=503,
                detail="Tenant isolation migration required for pod activation requests",
            ) from exc
        else:
            detail = str(exc.detail)
            if "23505" in detail or "duplicate key" in detail.lower():
                raise HTTPException(status_code=409, detail="Request already pending")
            raise
    except Exception:
        raise

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="request_pod_activation",
        resource_type="pod_activation_request",
        resource_id=created[0].get("id") if created else None,
        details={"model_id": model_id, "model_name": model_name, "domain": domain},
        previous_value=None,
        new_value={"status": "pending"},
    )
    # Same flow as approve/reject (client auth_audit): show user request on Auth Events tab.
    req_id = created[0].get("id") if created else None
    role_str = str(context.get("role") or "user")
    email_str = str((requester.get("email") or "")).strip()
    await insert_auth_audit_row(
        user_id=str(requester["id"]),
        email=email_str,
        role=role_str,
        event=f"request_pod:{model_id}",
        action_code="C",
        outcome_code=0,
        resource_type="pod_activation",
        resource_id=str(req_id) if req_id else None,
    )
    return {"success": True, "request": created[0] if created else None}


@router.get("/api/pod-activation/requests")
async def list_activation_requests(
    status: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    context = await get_user_context(authorization)
    requester_role = context.get("role")
    requester_tenant_id = context.get("tenant_id")
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    query = (
        "select=*"
        f"&tenant_id=eq.{quote(str(requester_tenant_id), safe='')}"
        "&order=requested_at.desc"
    )
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"

    try:
        rows = await postgrest_get("pod_activation_requests", query)
    except HTTPException as exc:
        if not _is_missing_tenant_column(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Tenant isolation migration required for pod activation requests",
        ) from exc
    if not rows:
        return {"requests": []}

    # Enrich requests with requester identity + tenant info.
    # This avoids relying on client-side RLS joins and guarantees tenant-scoped visibility.
    user_ids = [r.get("user_id") for r in rows if r.get("user_id")]
    if not user_ids:
        return {"requests": []}
    encoded_user_ids = ",".join(quote(str(uid), safe="") for uid in user_ids)

    # Dashboard rule: do not include requester/admin requests in admin queue metrics.
    admin_role_rows = await postgrest_get(
        "user_roles",
        f"select=user_id,role&user_id=in.({encoded_user_ids})&role=in.(admin,global_admin)",
    )
    admin_user_ids = {str(r.get("user_id")) for r in (admin_role_rows or []) if r.get("user_id")}

    app_users = await postgrest_get(
        "app_users",
        f"select=user_id,full_name,email,tenant_id&user_id=in.({encoded_user_ids})",
    )
    user_map = {str(u.get("user_id")): u for u in (app_users or []) if u.get("user_id")}

    tenant_ids = sorted({str(u.get("tenant_id")) for u in (app_users or []) if u.get("tenant_id")})
    tenants_map: dict[str, str] = {}
    if tenant_ids:
        encoded_tenant_ids = ",".join(quote(tid, safe="") for tid in tenant_ids)
        tenants = await postgrest_get(
            "tenants",
            f"select=id,name&id=in.({encoded_tenant_ids})",
        )
        tenants_map = {str(t.get("id")): str(t.get("name")) for t in tenants if t.get("id") and t.get("name") is not None}

    enriched: list[dict[str, object]] = []
    for r in rows:
        uid = r.get("user_id")
        if uid and str(uid) in admin_user_ids:
            continue
        u = user_map.get(str(uid)) if uid else None
        if not u:
            # Tenant isolation defense-in-depth: if we can't resolve tenant for the requester, don't return it.
            continue
        req_tenant_id = u.get("tenant_id")
        if not req_tenant_id or str(req_tenant_id) != str(requester_tenant_id):
            continue

        req_tenant_name = tenants_map.get(str(req_tenant_id))
        enriched.append(
            {
                **r,
                "requested_by_full_name": u.get("full_name"),
                "requested_by_email": u.get("email"),
                "requested_by_tenant_id": req_tenant_id,
                "requested_by_tenant_name": req_tenant_name,
            }
        )

    return {"requests": enriched}


@router.post("/api/pod-activation/{request_id}/approve")
async def approve_activation_request(
    request_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    context = await get_user_context(authorization)
    requester = context.get("user") or {}
    requester_role = context.get("role")
    requester_tenant_id = context.get("tenant_id")
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    try:
        requests = await postgrest_get(
            "pod_activation_requests",
            (
                "select=*"
                f"&id=eq.{quote(request_id, safe='')}"
                f"&tenant_id=eq.{quote(str(requester_tenant_id), safe='')}"
                "&limit=1"
            ),
        )
    except HTTPException as exc:
        if not _is_missing_tenant_column(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Tenant isolation migration required for pod activation requests",
        ) from exc
    if not requests:
        raise HTTPException(status_code=404, detail="Activation request not found")
    activation_request = requests[0]
    if activation_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")

    target_tenant_id = activation_request.get("tenant_id")
    if not target_tenant_id:
        app_users = await postgrest_get(
            "app_users",
            f"select=tenant_id&user_id=eq.{quote(str(activation_request['user_id']), safe='')}&limit=1",
        )
        target_tenant_id = app_users[0].get("tenant_id") if app_users else None
    if not target_tenant_id or str(target_tenant_id) != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant pod activation approval denied")

    existing = await postgrest_get(
        "activated_models",
        (
            "select=id"
            f"&user_id=eq.{quote(activation_request['user_id'], safe='')}"
            f"&model_id=eq.{quote(activation_request['model_id'], safe='')}"
            "&limit=1"
        ),
    )
    if not existing:
        await assert_tenant_may_add_distinct_model(
            str(target_tenant_id),
            str(activation_request.get("model_id") or ""),
        )
        await postgrest_insert(
            "activated_models",
            {
                "user_id": activation_request["user_id"],
                "model_id": activation_request["model_id"],
                "model_name": activation_request["model_name"],
                "domain": activation_request["domain"],
            },
        )
        await _sync_model_to_user_devices(
            user_id=str(activation_request["user_id"]),
            model_id=str(activation_request["model_id"]),
            model_name=str(activation_request.get("model_name") or ""),
            domain=str(activation_request.get("domain") or "unknown"),
            allocated_by=str(requester["id"]),
        )
        await try_emit_webhook_event(
            str(requester_tenant_id),
            WEBHOOK_EVENT_MODEL_DEPLOYED,
            {
                "user_id": str(activation_request["user_id"]),
                "model_id": str(activation_request["model_id"]),
                "model_name": str(activation_request.get("model_name") or ""),
                "domain": str(activation_request.get("domain") or ""),
            },
        )

    await postgrest_patch(
        "pod_activation_requests",
        f"id=eq.{quote(request_id, safe='')}",
        {
            "status": "approved",
            "reviewed_by": requester["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": None,
        },
    )
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="approve_pod",
        resource_type="pod_activation_request",
        resource_id=request_id,
        details={"model_id": activation_request.get("model_id")},
        previous_value={"status": "pending"},
        new_value={"status": "approved"},
    )
    return {"success": True}


@router.post("/api/pod-activation/{request_id}/reject")
async def reject_activation_request(
    request_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    context = await get_user_context(authorization)
    requester = context.get("user") or {}
    requester_role = context.get("role")
    requester_tenant_id = context.get("tenant_id")
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    try:
        requests = await postgrest_get(
            "pod_activation_requests",
            (
                "select=*"
                f"&id=eq.{quote(request_id, safe='')}"
                f"&tenant_id=eq.{quote(str(requester_tenant_id), safe='')}"
                "&limit=1"
            ),
        )
    except HTTPException as exc:
        if not _is_missing_tenant_column(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Tenant isolation migration required for pod activation requests",
        ) from exc
    if not requests:
        raise HTTPException(status_code=404, detail="Activation request not found")
    activation_request = requests[0]
    if activation_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected")

    target_tenant_id = activation_request.get("tenant_id")
    if not target_tenant_id:
        app_users = await postgrest_get(
            "app_users",
            f"select=tenant_id&user_id=eq.{quote(str(activation_request['user_id']), safe='')}&limit=1",
        )
        target_tenant_id = app_users[0].get("tenant_id") if app_users else None
    if not target_tenant_id or str(target_tenant_id) != str(requester_tenant_id):
        raise HTTPException(status_code=403, detail="Cross-tenant pod activation rejection denied")

    body = await request.json()
    rejection_reason = (body.get("rejection_reason") or "").strip() or None

    await postgrest_patch(
        "pod_activation_requests",
        f"id=eq.{quote(request_id, safe='')}",
        {
            "status": "rejected",
            "reviewed_by": requester["id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": rejection_reason,
        },
    )
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="reject_pod",
        resource_type="pod_activation_request",
        resource_id=request_id,
        details={"model_id": activation_request.get("model_id"), "rejection_reason": rejection_reason},
        previous_value={"status": "pending"},
        new_value={"status": "rejected"},
    )
    return {"success": True}


@router.get("/api/pod-activation/user/{user_id}/activations")
async def list_user_activations(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
):
    _, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")
    await _require_same_tenant_user(user_id, str(requester_tenant_id))

    rows = await postgrest_get(
        "activated_models",
        f"select=*&user_id=eq.{quote(user_id, safe='')}&order=activated_at.desc",
    )
    return {"allocations": rows}


@router.post("/api/pod-activation/allocate")
async def allocate_model_to_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    body = await request.json()
    user_id = (body.get("user_id") or "").strip()
    model_id = (body.get("model_id") or "").strip()
    model_name = (body.get("model_name") or "").strip()
    domain = (body.get("domain") or "").strip()
    if not user_id or not model_id or not model_name or domain not in VALID_DOMAINS:
        raise HTTPException(status_code=400, detail="user_id, model_id, model_name and valid domain are required")
    await _require_same_tenant_user(user_id, str(requester_tenant_id))

    existing = await postgrest_get(
        "activated_models",
        (
            "select=id"
            f"&user_id=eq.{quote(user_id, safe='')}"
            f"&model_id=eq.{quote(model_id, safe='')}"
            "&limit=1"
        ),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Model already allocated to user")

    await assert_tenant_may_add_distinct_model(str(requester_tenant_id), model_id)

    created = await postgrest_insert(
        "activated_models",
        {
            "user_id": user_id,
            "model_id": model_id,
            "model_name": model_name,
            "domain": domain,
        },
    )
    await _sync_model_to_user_devices(user_id, model_id, model_name, domain, str(requester["id"]))
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="allocate_model",
        resource_type="activated_model",
        resource_id=model_id,
        details={"target_user_id": user_id, "model_name": model_name, "domain": domain},
        previous_value=None,
        new_value={"model_id": model_id, "domain": domain},
    )
    await try_emit_webhook_event(
        str(requester_tenant_id),
        WEBHOOK_EVENT_MODEL_DEPLOYED,
        {
            "user_id": user_id,
            "model_id": model_id,
            "model_name": model_name,
            "domain": domain,
        },
    )
    return {"success": True, "allocation": created[0] if created else None}


@router.delete("/api/pod-activation/allocations/{allocation_id}")
async def deallocate_model(
    allocation_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role, requester_tenant_id = await _get_requester_role(authorization)
    _require_admin(requester_role)
    if not requester_tenant_id:
        raise HTTPException(status_code=403, detail="Requester is not linked to a tenant")

    allocation_rows = await postgrest_get(
        "activated_models",
        f"select=id,model_id,user_id&id=eq.{quote(allocation_id, safe='')}&limit=1",
    )
    if not allocation_rows:
        raise HTTPException(status_code=404, detail="Allocation not found")
    allocation_user_id = str(allocation_rows[0].get("user_id") or "")
    if not allocation_user_id:
        raise HTTPException(status_code=400, detail="Invalid allocation ownership")
    await _require_same_tenant_user(allocation_user_id, str(requester_tenant_id))

    await postgrest_delete(
        "activated_models",
        f"id=eq.{quote(allocation_id, safe='')}",
    )
    await _remove_model_from_user_devices(
        allocation_user_id, str(allocation_rows[0].get("model_id") or "")
    )
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="deallocate_model",
        resource_type="activated_model",
        resource_id=allocation_id,
        details={"model_id": allocation_rows[0].get("model_id"), "target_user_id": allocation_rows[0].get("user_id")},
        previous_value={"model_id": allocation_rows[0].get("model_id"), "domain": allocation_rows[0].get("domain")},
        new_value=None,
    )
    return {"success": True}


@router.delete("/api/pod-activation/my-models/{model_id}")
async def delete_my_model_data(
    model_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Delete a model allocation and related user-scoped data for this user."""
    requester = await verify_user(authorization)
    user_id = requester["id"]
    normalized_model_id = (model_id or "").strip()
    if not normalized_model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    quoted_user_id = quote(user_id, safe="")
    quoted_model_id = quote(normalized_model_id, safe="")

    # Remove chat messages for this user's conversations for this model first.
    conversations = await postgrest_get(
        "chat_conversations",
        (
            "select=id"
            f"&user_id=eq.{quoted_user_id}"
            f"&model_id=eq.{quoted_model_id}"
        ),
    )
    conversation_ids = [str(row.get("id")) for row in conversations if row.get("id")]
    if conversation_ids:
        encoded_ids = ",".join(quote(cid, safe="") for cid in conversation_ids)
        await postgrest_delete(
            "chat_messages",
            f"conversation_id=in.({encoded_ids})",
        )

    # Remove known user-scoped records tied to this model.
    # Run independent deletions in parallel to reduce end-user wait time.
    await asyncio.gather(
        postgrest_delete(
            "chat_conversations",
            (
                f"user_id=eq.{quoted_user_id}"
                f"&model_id=eq.{quoted_model_id}"
            ),
        ),
        postgrest_delete(
            "agent_schedules",
            (
                f"user_id=eq.{quoted_user_id}"
                f"&model_id=eq.{quoted_model_id}"
            ),
        ),
        postgrest_delete(
            "pod_activation_requests",
            (
                f"user_id=eq.{quoted_user_id}"
                f"&model_id=eq.{quoted_model_id}"
            ),
        ),
        postgrest_delete(
            "activated_models",
            (
                f"user_id=eq.{quoted_user_id}"
                f"&model_id=eq.{quoted_model_id}"
            ),
        ),
    )
    await _remove_model_from_user_devices(user_id, normalized_model_id)

    await insert_audit_log(
        request=request,
        user_id=user_id,
        action="delete_my_model_data",
        resource_type="activated_model",
        resource_id=normalized_model_id,
        details={"model_id": normalized_model_id},
        previous_value={"model_id": normalized_model_id},
        new_value=None,
    )
    return {"success": True}
