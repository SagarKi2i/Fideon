from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import insert_audit_log, postgrest_delete, postgrest_get, postgrest_insert, postgrest_patch, verify_user

router = APIRouter()
VALID_STATUSES = {"pending", "approved", "rejected"}
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
    requester = await verify_user(authorization)
    query = f"select=*&user_id=eq.{quote(requester['id'], safe='')}&order=requested_at.desc"
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"
    rows = await postgrest_get("pod_activation_requests", query)
    return {"requests": rows}


@router.post("/api/pod-activation/request")
async def create_activation_request(request: Request, authorization: Optional[str] = Header(default=None)):
    requester = await verify_user(authorization)
    body = await request.json()
    model_id = (body.get("model_id") or "").strip()
    model_name = (body.get("model_name") or "").strip()
    domain = (body.get("domain") or "").strip()

    if not model_id or not model_name or domain not in VALID_DOMAINS:
        raise HTTPException(status_code=400, detail="model_id, model_name and valid domain are required")

    try:
        created = await postgrest_insert(
            "pod_activation_requests",
            {
                "user_id": requester["id"],
                "model_id": model_id,
                "model_name": model_name,
                "domain": domain,
                "status": "pending",
            },
        )
    except HTTPException as exc:
        detail = str(exc.detail)
        if "23505" in detail or "duplicate key" in detail.lower():
            raise HTTPException(status_code=409, detail="Request already pending")
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
    return {"success": True, "request": created[0] if created else None}


@router.get("/api/pod-activation/requests")
async def list_activation_requests(
    status: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    _, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    query = "select=*&order=requested_at.desc"
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"

    rows = await postgrest_get("pod_activation_requests", query)
    return {"requests": rows}


@router.post("/api/pod-activation/{request_id}/approve")
async def approve_activation_request(
    request_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    requests = await postgrest_get(
        "pod_activation_requests",
        f"select=*&id=eq.{quote(request_id, safe='')}&limit=1",
    )
    if not requests:
        raise HTTPException(status_code=404, detail="Activation request not found")
    activation_request = requests[0]
    if activation_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")

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
        await postgrest_insert(
            "activated_models",
            {
                "user_id": activation_request["user_id"],
                "model_id": activation_request["model_id"],
                "model_name": activation_request["model_name"],
                "domain": activation_request["domain"],
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
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    requests = await postgrest_get(
        "pod_activation_requests",
        f"select=*&id=eq.{quote(request_id, safe='')}&limit=1",
    )
    if not requests:
        raise HTTPException(status_code=404, detail="Activation request not found")
    activation_request = requests[0]
    if activation_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected")

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
    _, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

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
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    body = await request.json()
    user_id = (body.get("user_id") or "").strip()
    model_id = (body.get("model_id") or "").strip()
    model_name = (body.get("model_name") or "").strip()
    domain = (body.get("domain") or "").strip()
    if not user_id or not model_id or not model_name or domain not in VALID_DOMAINS:
        raise HTTPException(status_code=400, detail="user_id, model_id, model_name and valid domain are required")

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

    created = await postgrest_insert(
        "activated_models",
        {
            "user_id": user_id,
            "model_id": model_id,
            "model_name": model_name,
            "domain": domain,
        },
    )
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
    return {"success": True, "allocation": created[0] if created else None}


@router.delete("/api/pod-activation/allocations/{allocation_id}")
async def deallocate_model(
    allocation_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    allocation_rows = await postgrest_get(
        "activated_models",
        f"select=id,model_id,user_id&id=eq.{quote(allocation_id, safe='')}&limit=1",
    )
    if not allocation_rows:
        raise HTTPException(status_code=404, detail="Allocation not found")

    await postgrest_delete(
        "activated_models",
        f"id=eq.{quote(allocation_id, safe='')}",
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
