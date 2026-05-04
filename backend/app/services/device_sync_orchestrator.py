"""
Device Sync Orchestrator — FNF-193

Background loop that drives the model distribution pipeline:

  1. Every DEVICE_SYNC_ORCHESTRATOR_POLL_SECONDS seconds, scan for online devices
     that have undownloaded model allocations (device_models.is_downloaded = false).
  2. For each such device, write a device_sync_logs row (sync_type='model_sync',
     status='success') so the Electron client and admin UI receive a Supabase
     realtime push and know to pull the pending model list.
  3. Skips devices that already received a sync log in the last DEVICE_SYNC_MIN_GAP_SECONDS
     to avoid flooding the log table with duplicate entries.

This is intentionally lightweight — it does NOT do any model transfer itself.
The Electron client polls /api/v1/devices/models on heartbeat or when it receives
the realtime push and then triggers Ollama pull locally.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx
import structlog

from app.core.config import SUPABASE_URL
from app.core.supabase import postgrest_get, postgrest_insert, service_headers

log = structlog.get_logger("device_sync_orchestrator")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _log_sync_event(device_id: str, model_ids: list[str]) -> None:
    """Insert a device_sync_logs row to notify the device of pending models."""
    await postgrest_insert(
        "device_sync_logs",
        {
            "device_id": device_id,
            "sync_type": "model_sync",
            "status": "success",
            "details": {"pending_model_ids": model_ids, "dispatched_by": "orchestrator"},
        },
    )


async def dispatch_pending_models(*, min_gap_seconds: float = 300.0) -> int:
    """
    Core sweep: find online devices with undownloaded models and emit sync events.

    Returns the number of devices that received a sync notification.
    """
    now = _utc_now()
    gap_cutoff = _iso(now - timedelta(seconds=max(60.0, min_gap_seconds)))

    # Fetch online, active devices
    online_devices = await postgrest_get(
        "devices",
        "select=id&status=eq.online&is_active=eq.true&limit=500",
    )
    if not online_devices:
        return 0

    notified = 0
    for device in online_devices:
        device_id = str(device.get("id") or "")
        if not device_id:
            continue

        # Check if we already sent a sync event recently for this device
        recent_logs = await postgrest_get(
            "device_sync_logs",
            (
                f"select=id&device_id=eq.{quote(device_id, safe='')}"
                f"&sync_type=eq.model_sync"
                f"&created_at=gt.{quote(gap_cutoff, safe='')}"
                f"&limit=1"
            ),
        )
        if recent_logs:
            continue  # Notified recently — skip

        # Check for undownloaded model allocations
        pending = await postgrest_get(
            "device_models",
            (
                f"select=model_id&device_id=eq.{quote(device_id, safe='')}"
                f"&is_downloaded=eq.false&limit=50"
            ),
        )
        if not pending:
            continue

        pending_ids = [str(r.get("model_id")) for r in pending if r.get("model_id")]
        if not pending_ids:
            continue

        try:
            await _log_sync_event(device_id, pending_ids)
            notified += 1
            log.info(
                "device_sync_orchestrator.dispatched",
                device_id=device_id,
                pending_count=len(pending_ids),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "device_sync_orchestrator.dispatch_failed",
                device_id=device_id,
                error=str(exc),
            )

    return notified


async def trigger_device_sync(device_id: str, model_ids: Optional[list[str]] = None) -> None:
    """
    Immediately emit a sync event for a specific device.
    Used by the admin trigger-sync endpoint and the model allocation endpoint.

    If model_ids is None, fetches all undownloaded model IDs for the device.
    """
    if model_ids is None:
        pending = await postgrest_get(
            "device_models",
            f"select=model_id&device_id=eq.{quote(device_id, safe='')}&is_downloaded=eq.false&limit=50",
        )
        model_ids = [str(r.get("model_id")) for r in (pending or []) if r.get("model_id")]

    await postgrest_insert(
        "device_sync_logs",
        {
            "device_id": device_id,
            "sync_type": "model_sync",
            "status": "success",
            "details": {
                "pending_model_ids": model_ids,
                "dispatched_by": "admin",
            },
        },
    )
    log.info("device_sync_orchestrator.manual_trigger", device_id=device_id, model_count=len(model_ids))


async def broadcast_tenant_sync(tenant_id: str) -> int:
    """
    Emit a sync event for ALL online devices belonging to a tenant.
    Returns the number of devices notified.
    """
    online_devices = await postgrest_get(
        "devices",
        (
            f"select=id&tenant_id=eq.{quote(tenant_id, safe='')}"
            f"&status=eq.online&is_active=eq.true&limit=500"
        ),
    )
    if not online_devices:
        return 0

    notified = 0
    for device in online_devices:
        device_id = str(device.get("id") or "")
        if not device_id:
            continue
        try:
            await trigger_device_sync(device_id)
            notified += 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "device_sync_orchestrator.broadcast_device_failed",
                device_id=device_id,
                error=str(exc),
            )

    log.info("device_sync_orchestrator.broadcast_complete", tenant_id=tenant_id, notified=notified)
    return notified


async def orchestrator_loop(
    *,
    poll_seconds: Optional[float] = None,
    min_gap_seconds: Optional[float] = None,
) -> None:
    """
    Background task registered in factory.py alongside device_offline_detector.
    Polls for pending model distributions and emits realtime sync events.
    """
    from app.core.config import (
        DEVICE_SYNC_ORCHESTRATOR_POLL_SECONDS,
        DEVICE_SYNC_MIN_GAP_SECONDS,
    )

    poll = float(poll_seconds if poll_seconds is not None else DEVICE_SYNC_ORCHESTRATOR_POLL_SECONDS)
    gap = float(min_gap_seconds if min_gap_seconds is not None else DEVICE_SYNC_MIN_GAP_SECONDS)

    poll = max(30.0, min(600.0, poll))
    gap = max(60.0, gap)

    log.info("device_sync_orchestrator.started", poll_seconds=poll, min_gap_seconds=gap)

    consecutive_failures = 0
    while True:
        await asyncio.sleep(poll)
        try:
            notified = await dispatch_pending_models(min_gap_seconds=gap)
            if notified:
                log.info("device_sync_orchestrator.sweep_done", notified=notified)
            consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            log.warning(
                "device_sync_orchestrator.sweep_failed",
                error=str(exc),
                consecutive=consecutive_failures,
            )