"""
Admin API for Federated Learning round management.

Endpoints (all require admin or global_admin role):

  POST /api/v1/admin/federated/rounds/start
      Start a new 'collecting' round for a model.
      Body: { model_id, min_participants, description? }

  GET  /api/v1/admin/federated/rounds
      List all rounds with participant counts and status.
      Query params: model_id (optional), status (optional), limit (default 20)

  POST /api/v1/admin/federated/rounds/{round_id}/aggregate
      Trigger FedAvg + Azure Blob upload + quantization for a round that is
      in 'aggregating' status. Proxies to the RunPod AI/ML server; returns immediately.

  POST /api/v1/admin/federated/rounds/{round_id}/close
      Force-close a round without aggregating (e.g. insufficient contributions).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.core.supabase import postgrest_get, postgrest_insert, postgrest_patch, verify_user

log = structlog.get_logger("federated_admin")
router = APIRouter()

_ADMIN_ROLES = {"admin", "global_admin"}


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def _require_admin(authorization: Optional[str]) -> dict:
    user = await verify_user(authorization)
    rows = await postgrest_get(
        "user_roles",
        f"select=role&user_id=eq.{quote(user['id'], safe='')}&limit=1",
    )
    role = rows[0].get("role") if rows else None
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Background aggregation task
# ---------------------------------------------------------------------------

def _run_aggregation_bg(
    round_id: str,
    model_id: str,
    round_number: int,
    log_lines: list[str],
    runpod_url: str,
) -> None:
    """Runs in a thread — proxies FedAvg to the RunPod AI/ML server pipeline."""
    import requests as _requests

    log_lines.append(f"[federated_admin] Proxying aggregation to RunPod: {runpod_url}/federated/start\n")
    try:
        resp = _requests.post(f"{runpod_url}/federated/start", json={}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        log_lines.append(f"[federated_admin] RunPod response: {data}\n")
        log.info(
            "federated_admin.aggregation_proxied",
            round_id=round_id,
            runpod_job=data.get("job_id"),
        )
    except Exception as exc:
        log.error(
            "federated_admin.aggregation_proxy_failed",
            round_id=round_id,
            error=str(exc),
        )
        log_lines.append(f"[federated_admin] ERROR: {exc}\n")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/api/v1/admin/federated/rounds/start")
async def start_federated_round(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    Start a new federated learning round in 'collecting' status.

    Body:
      model_id         (str, required) — identifier of the model being updated
      min_participants (int, default 2) — minimum submissions before auto-aggregation
      description      (str, optional)
    """
    await _require_admin(authorization)
    body = await request.json()

    model_id = str(body.get("model_id") or "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    min_participants = int(body.get("min_participants") or 2)
    if min_participants < 1:
        raise HTTPException(status_code=400, detail="min_participants must be >= 1")

    # Determine next round number for this model
    existing = await postgrest_get(
        "federated_rounds",
        f"select=round_number&model_id=eq.{quote(model_id, safe='')}&order=round_number.desc&limit=1",
    )
    next_round = (int(existing[0]["round_number"]) + 1) if existing else 1

    row = await postgrest_insert(
        "federated_rounds",
        {
            "model_id": model_id,
            "round_number": next_round,
            "status": "collecting",
            "min_participants": min_participants,
            "current_participants": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "description": body.get("description") or "",
        },
    )

    log.info("federated_admin.round_started", model_id=model_id, round_number=next_round)
    return {
        "success": True,
        "round_id": row[0]["id"],
        "round_number": next_round,
        "model_id": model_id,
        "min_participants": min_participants,
        "status": "collecting",
    }


@router.get("/api/v1/admin/federated/rounds")
async def list_federated_rounds(
    model_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    authorization: Optional[str] = Header(default=None),
):
    """List federated rounds with participant counts, optionally filtered."""
    await _require_admin(authorization)

    parts = [
        "select=id,model_id,round_number,status,min_participants,"
        "current_participants,started_at,completed_at,description,aggregated_version",
        f"order=started_at.desc",
        f"limit={min(limit, 100)}",
    ]
    if model_id:
        parts.append(f"model_id=eq.{quote(model_id, safe='')}")
    if status:
        parts.append(f"status=eq.{quote(status, safe='')}")

    rounds = await postgrest_get("federated_rounds", "&".join(parts))
    return {"rounds": rounds or [], "count": len(rounds or [])}


@router.post("/api/v1/admin/federated/rounds/{round_id}/aggregate")
async def trigger_aggregation(
    round_id: str,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
):
    """
    Trigger FedAvg aggregation for a round.

    The round must be in 'aggregating' status (reached min_participants).
    The pipeline runs in the background; this endpoint returns immediately.

    Steps executed in background via RunPod AI/ML server:
      FedAvg of all uploaded weight versions in Azure Blob ->
      Quantize -> GGUF -> upload back to Azure Blob -> adapter_registry ->
      Round marked completed
    """
    from app.core.config import RUNPOD_PROXY_BASE_URL
    if not RUNPOD_PROXY_BASE_URL:
        raise HTTPException(
            status_code=503,
            detail="RUNPOD_PROXY_BASE_URL is not configured — cannot reach the AI/ML server",
        )
    await _require_admin(authorization)

    rows = await postgrest_get(
        "federated_rounds",
        f"select=*&id=eq.{quote(round_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Round not found")

    round_row = rows[0]
    current_status = round_row.get("status")

    # Allow triggering from both 'aggregating' (auto-threshold reached) and
    # 'collecting' (admin wants to force-aggregate early).
    if current_status not in {"collecting", "aggregating"}:
        raise HTTPException(
            status_code=409,
            detail=f"Round is '{current_status}' — can only aggregate from collecting/aggregating",
        )

    model_id = round_row.get("model_id")
    round_number = int(round_row.get("round_number") or 0)
    current_participants = int(round_row.get("current_participants") or 0)

    if current_participants == 0:
        raise HTTPException(
            status_code=409,
            detail="Round has 0 participant submissions — nothing to aggregate",
        )

    # Transition to aggregating so devices know collection is closed
    await postgrest_patch(
        "federated_rounds",
        f"id=eq.{quote(round_id, safe='')}",
        {"status": "aggregating"},
    )

    log_lines: list[str] = []
    background_tasks.add_task(
        asyncio.to_thread,
        _run_aggregation_bg,
        round_id,
        model_id,
        round_number,
        log_lines,
        RUNPOD_PROXY_BASE_URL,
    )

    log.info(
        "federated_admin.aggregation_triggered",
        round_id=round_id,
        model_id=model_id,
        round_number=round_number,
        participants=current_participants,
    )
    return {
        "success": True,
        "message": (
            f"Aggregation started for round {round_number} "
            f"({current_participants} participant(s)). "
            "Round will be marked 'completed' when done."
        ),
        "round_id": round_id,
        "model_id": model_id,
        "round_number": round_number,
        "participants": current_participants,
    }


@router.post("/api/v1/admin/federated/rounds/{round_id}/close")
async def close_round(
    round_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    Force-close a round without aggregating (e.g. not enough participants).
    Body: { reason?: str }
    """
    await _require_admin(authorization)

    rows = await postgrest_get(
        "federated_rounds",
        f"select=status&id=eq.{quote(round_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Round not found")
    if rows[0].get("status") == "completed":
        raise HTTPException(status_code=409, detail="Round is already completed")

    body = await request.json()
    await postgrest_patch(
        "federated_rounds",
        f"id=eq.{quote(round_id, safe='')}",
        {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "description": body.get("reason") or "closed by admin without aggregation",
        },
    )
    return {"success": True, "round_id": round_id, "status": "completed"}
