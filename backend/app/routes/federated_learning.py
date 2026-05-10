import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

import jwt
import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.core.config import DEVICE_JWT_SECRET
from app.core.supabase import get_device_by_token, postgrest_get, postgrest_insert, postgrest_patch

log = structlog.get_logger("federated_learning")

router = APIRouter()


def _device_id(device: dict[str, Any]) -> str:
    return str(device["id"])


def _parse_utc_iso(value: Any) -> datetime:
    raw = str(value)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _verify_device_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, DEVICE_JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Device token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid device token")


def _enforce_not_revoked(claims: dict[str, Any], jwt_issued_after_raw: Any) -> None:
    if not jwt_issued_after_raw:
        return
    try:
        issued_after_ts = _parse_utc_iso(jwt_issued_after_raw).timestamp()
    except ValueError:
        issued_after_ts = 0
    if claims.get("iat", 0) < issued_after_ts:
        raise HTTPException(status_code=401, detail="Device token has been revoked — please re-register")


async def _resolve_device_auth(
    authorization: Optional[str],
    x_device_token: Optional[str],
) -> dict[str, Any]:
    # Primary auth contract for v1 device APIs: Bearer device JWT.
    if authorization and authorization.lower().startswith("bearer "):
        claims = _verify_device_jwt(authorization.split(" ", 1)[1])
        device_id = str(claims.get("device_id") or "")
        if not device_id:
            raise HTTPException(status_code=401, detail="Invalid device JWT claims")
        rows = await postgrest_get(
            "devices",
            f"select=id,is_active,jwt_issued_after&id=eq.{quote(device_id, safe='')}&limit=1",
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Device not found")
        device = rows[0]
        if not device.get("is_active", False):
            raise HTTPException(status_code=403, detail="Device is deactivated")
        _enforce_not_revoked(claims, device.get("jwt_issued_after"))
        return {"id": device_id}

    # Backward compatibility path for older clients.
    if x_device_token:
        return await get_device_by_token(x_device_token)

    raise HTTPException(status_code=401, detail="Device JWT required")


async def _action_get_feedback(device: dict[str, Any], model_id: Optional[str], unused_only: bool) -> dict[str, Any]:
    query = f"select=*&device_id=eq.{quote(_device_id(device), safe='')}&order=created_at.desc"
    if model_id:
        query += f"&model_id=eq.{quote(model_id, safe='')}"
    if unused_only:
        query += "&is_used_for_training=eq.false"
    rows = await postgrest_get("training_feedback", query)
    return {"success": True, "feedback": rows}


async def _action_get_training_jobs(device: dict[str, Any]) -> dict[str, Any]:
    rows = await postgrest_get(
        "training_jobs",
        f"select=*&device_id=eq.{quote(_device_id(device), safe='')}&order=created_at.desc",
    )
    return {"success": True, "jobs": rows}


async def _action_get_active_rounds(device: dict[str, Any]) -> dict[str, Any]:
    rounds = await postgrest_get(
        "federated_rounds",
        "select=*&status=in.(collecting,aggregating,completed)&order=started_at.desc",
    )
    contributions = await postgrest_get(
        "federated_updates",
        f"select=model_id,round_number,status,submitted_at&device_id=eq.{quote(_device_id(device), safe='')}",
    )
    return {"success": True, "rounds": rounds, "contributions": contributions}


async def _action_get_stats(device: dict[str, Any]) -> dict[str, Any]:
    feedback = await postgrest_get("training_feedback", f"select=id&device_id=eq.{quote(_device_id(device), safe='')}")
    jobs = await postgrest_get("training_jobs", f"select=id&device_id=eq.{quote(_device_id(device), safe='')}")
    contribs = await postgrest_get("federated_updates", f"select=id&device_id=eq.{quote(_device_id(device), safe='')}")
    return {
        "success": True,
        "stats": {
            "total_feedback": len(feedback),
            "total_training_jobs": len(jobs),
            "total_contributions": len(contribs),
        },
    }


async def _action_submit_feedback(device: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    rows = await postgrest_insert(
        "training_feedback",
        {
            "device_id": device["id"],
            "model_id": body.get("model_id"),
            "prompt": body.get("prompt"),
            "original_response": body.get("original_response"),
            "corrected_response": body.get("corrected_response"),
            "rating": body.get("rating"),
            "feedback_type": body.get("feedback_type") or "correction",
        },
    )
    return {"success": True, "feedback_id": rows[0]["id"]}


async def _action_create_training_job(device: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    feedback = await postgrest_get(
        "training_feedback",
        (
            f"select=id&device_id=eq.{quote(_device_id(device), safe='')}"
            f"&model_id=eq.{quote(str(body.get('model_id')), safe='')}"
            "&is_used_for_training=eq.false"
        ),
    )
    rows = await postgrest_insert(
        "training_jobs",
        {
            "device_id": device["id"],
            "model_id": body.get("model_id"),
            "training_type": body.get("training_type") or "lora",
            "config": body.get("config") or {},
            "feedback_count": len(feedback),
        },
    )
    await postgrest_patch(
        "training_feedback",
        (
            f"device_id=eq.{quote(_device_id(device), safe='')}"
            f"&model_id=eq.{quote(str(body.get('model_id')), safe='')}"
            "&is_used_for_training=eq.false"
        ),
        {"is_used_for_training": True},
    )
    return {"success": True, "job": rows[0]}


async def _action_update_training_job(device: dict[str, Any], body: dict[str, Any], now_iso: str) -> dict[str, Any]:
    update_data: Dict[str, Any] = {"status": body.get("status"), "updated_at": now_iso}
    if body.get("metrics") is not None:
        update_data["metrics"] = body.get("metrics")
    if body.get("error_message"):
        update_data["error_message"] = body.get("error_message")
    if body.get("status") == "running":
        update_data["started_at"] = now_iso
    if body.get("status") in ("completed", "failed"):
        update_data["completed_at"] = now_iso
    await postgrest_patch(
        "training_jobs",
        f"id=eq.{quote(str(body.get('job_id')), safe='')}&device_id=eq.{quote(_device_id(device), safe='')}",
        update_data,
    )
    return {"success": True}


async def _action_submit_gradient(
    device: dict[str, Any],
    body: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    model = str(body.get("model_id"))
    round_number = int(body.get("round_number"))
    rounds = await postgrest_get(
        "federated_rounds",
        (
            f"select=*&model_id=eq.{quote(model, safe='')}"
            f"&round_number=eq.{round_number}&status=eq.collecting&limit=1"
        ),
    )
    if not rounds:
        raise HTTPException(status_code=404, detail="No active federated round for this model")
    round_data = rounds[0]
    # Directory prefix so device can upload multiple adapter files (safetensors + config)
    storage_path = f"gradients/{model}/round-{round_number}/{device['id']}"
    rows = await postgrest_insert(
        "federated_updates",
        {
            "device_id": device["id"],
            "model_id": model,
            "round_number": round_number,
            "gradient_hash": body.get("gradient_hash"),
            "gradient_size_bytes": body.get("gradient_size_bytes") or 0,
            "storage_path": storage_path,
            "metrics": body.get("metrics") or {},
            "privacy_noise_added": body.get("privacy_noise_added", True),
        },
    )
    participants = int(round_data.get("current_participants") or 0) + 1
    await postgrest_patch(
        "federated_rounds",
        f"id=eq.{quote(round_data['id'], safe='')}",
        {"current_participants": participants},
    )
    threshold_reached = participants >= int(round_data.get("min_participants") or 0)
    if threshold_reached:
        await postgrest_patch(
            "federated_rounds",
            f"id=eq.{quote(round_data['id'], safe='')}",
            {"status": "aggregating"},
        )
        log.info(
            "federated.threshold_reached",
            round_id=round_data["id"],
            model_id=model,
            participants=participants,
        )
        # Auto-trigger FedAvg aggregation in background
        background_tasks.add_task(
            asyncio.to_thread,
            _trigger_aggregation_bg,
            round_data["id"],
            model,
            round_number,
        )

    return {
        "success": True,
        "update_id": rows[0]["id"],
        "storage_path": storage_path,
        "current_participants": participants,
        "aggregation_triggered": threshold_reached,
    }


async def _action_upload_gradient(device: dict[str, Any], request: Request) -> dict[str, Any]:
    """
    Upload a LoRA adapter file for this device's gradient contribution.

    Query params:
      model_id      — model being updated
      round_number  — federated round number
      filename      — target filename (e.g. adapter_model.safetensors)

    Body: raw binary file content (multipart or raw bytes)

    The file is stored in SeaweedFS at:
      gradients/{model_id}/round-{N}/{device_id}/{filename}
    """
    import os
    from app.core.config import SEAWEEDFS_BUCKET, SEAWEEDFS_ENDPOINT, SEAWEEDFS_ACCESS_KEY, SEAWEEDFS_SECRET_KEY
    import boto3
    from botocore.config import Config

    model_id = request.query_params.get("model_id", "").strip()
    round_number = request.query_params.get("round_number", "").strip()
    filename = request.query_params.get("filename", "adapter_model.safetensors").strip()

    if not model_id or not round_number:
        raise HTTPException(status_code=400, detail="model_id and round_number are required")
    if not filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Verify round is still collecting
    rounds = await postgrest_get(
        "federated_rounds",
        (
            f"select=id,status&model_id=eq.{quote(model_id, safe='')}"
            f"&round_number=eq.{round_number}&limit=1"
        ),
    )
    if not rounds or rounds[0].get("status") not in {"collecting", "aggregating"}:
        raise HTTPException(status_code=404, detail="No active round for this model/round_number")

    if not all([SEAWEEDFS_ENDPOINT, SEAWEEDFS_ACCESS_KEY, SEAWEEDFS_SECRET_KEY, SEAWEEDFS_BUCKET]):
        raise HTTPException(status_code=503, detail="SeaweedFS not configured on this server")

    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Request body is empty")

    key = f"gradients/{model_id}/round-{round_number}/{device['id']}/{filename}"
    s3 = boto3.client(
        "s3",
        endpoint_url=SEAWEEDFS_ENDPOINT,
        aws_access_key_id=SEAWEEDFS_ACCESS_KEY,
        aws_secret_access_key=SEAWEEDFS_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )
    s3.put_object(Bucket=SEAWEEDFS_BUCKET, Key=key, Body=body_bytes)

    log.info(
        "federated.gradient_uploaded",
        device_id=device["id"],
        model_id=model_id,
        round_number=round_number,
        key=key,
        size=len(body_bytes),
    )
    return {
        "success": True,
        "storage_key": key,
        "size_bytes": len(body_bytes),
    }


def _trigger_aggregation_bg(round_id: str, model_id: str, round_number: int) -> None:
    """Background thread entry-point for FedAvg aggregation."""
    from fine_tuning.federated_aggregator import run_aggregation
    result = run_aggregation(round_id, model_id, round_number)
    if result.success:
        log.info(
            "federated.auto_aggregation_complete",
            round_id=round_id,
            new_version=result.new_version,
        )
    else:
        log.error(
            "federated.auto_aggregation_failed",
            round_id=round_id,
            error=result.error,
        )


@router.api_route("/api/federated-learning", methods=["GET", "POST"])
async def federated_learning(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
    x_device_token: Optional[str] = Header(default=None),
):
    device = await _resolve_device_auth(authorization, x_device_token)
    action = request.query_params.get("action")

    # --- GET actions ---
    if action == "get-feedback":
        return await _action_get_feedback(
            device=device,
            model_id=request.query_params.get("model_id"),
            unused_only=request.query_params.get("unused") == "true",
        )
    if action == "get-training-jobs":
        return await _action_get_training_jobs(device)
    if action == "get-active-rounds":
        return await _action_get_active_rounds(device)
    if action == "get-stats":
        return await _action_get_stats(device)

    # --- File upload action (raw body, no JSON parse) ---
    if action == "upload-gradient":
        return await _action_upload_gradient(device, request)

    # --- POST actions (JSON body) ---
    body = await request.json()
    now_iso = datetime.now(timezone.utc).isoformat()
    if action == "submit-feedback":
        return await _action_submit_feedback(device, body)
    if action == "create-training-job":
        return await _action_create_training_job(device, body)
    if action == "update-training-job":
        return await _action_update_training_job(device, body, now_iso)
    if action == "submit-gradient":
        return await _action_submit_gradient(device, body, background_tasks)

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
