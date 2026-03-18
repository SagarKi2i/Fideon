from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import get_device_by_token, postgrest_get, postgrest_insert, postgrest_patch

router = APIRouter()


def _device_id(device: dict[str, Any]) -> str:
    return str(device["id"])


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


async def _action_submit_gradient(device: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
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
    storage_path = f"gradients/{model}/round-{round_number}/{device['id']}.bin"
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
    if participants >= int(round_data.get("min_participants") or 0):
        await postgrest_patch(
            "federated_rounds",
            f"id=eq.{quote(round_data['id'], safe='')}",
            {"status": "aggregating"},
        )
    return {"success": True, "update_id": rows[0]["id"], "storage_path": storage_path}


@router.api_route("/api/federated-learning", methods=["GET", "POST"])
async def federated_learning(request: Request, x_device_token: Optional[str] = Header(default=None)):
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
    device = await get_device_by_token(x_device_token)
    action = request.query_params.get("action")
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

    body = await request.json()
    now_iso = datetime.now(timezone.utc).isoformat()
    if action == "submit-feedback":
        return await _action_submit_feedback(device, body)
    if action == "create-training-job":
        return await _action_create_training_job(device, body)
    if action == "update-training-job":
        return await _action_update_training_job(device, body, now_iso)
    if action == "submit-gradient":
        return await _action_submit_gradient(device, body)

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
