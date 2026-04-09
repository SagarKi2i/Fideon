import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

import structlog

from app.core.config import DEVICE_OFFLINE_AFTER_SECONDS, DEVICE_OFFLINE_DETECTOR_POLL_SECONDS
from app.core.supabase import postgrest_patch

log = structlog.get_logger("device_offline_detector")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def mark_stale_online_devices_offline(*, older_than_seconds: float) -> None:
    """
    Best-effort sweep: any device with status=online and last_seen_at older than threshold becomes offline.

    This is required because heartbeats are push-based; without a sweep, devices can remain "online"
    indefinitely if a client stops heartbeating (app closed/offline).
    """
    cutoff = _utc_now() - timedelta(seconds=max(1.0, float(older_than_seconds)))
    cutoff_iso = _iso(cutoff)

    # PostgREST can update multiple rows via a filter query.
    # Note: last_seen_at is TIMESTAMPTZ in DB; compare against UTC ISO.
    query = (
        "status=eq.online"
        "&is_active=eq.true"
        f"&last_seen_at=lt.{quote(cutoff_iso, safe='')}"
    )
    await postgrest_patch(
        "devices",
        query,
        {"status": "offline"},
    )


async def offline_detector_loop(
    *,
    poll_seconds: Optional[float] = None,
    offline_after_seconds: Optional[float] = None,
) -> None:
    """
    Background loop that keeps device status correct.

    Defaults are controlled by env vars in app.core.config.
    """
    poll = float(poll_seconds if poll_seconds is not None else DEVICE_OFFLINE_DETECTOR_POLL_SECONDS)
    offline_after = float(
        offline_after_seconds if offline_after_seconds is not None else DEVICE_OFFLINE_AFTER_SECONDS
    )

    # Defensive bounds (avoid accidental hot loops).
    poll = max(5.0, min(300.0, poll))
    offline_after = max(30.0, offline_after)

    log.info(
        "device_offline_detector.started",
        poll_seconds=poll,
        offline_after_seconds=offline_after,
    )

    consecutive_failures = 0
    while True:
        await asyncio.sleep(poll)
        try:
            await mark_stale_online_devices_offline(older_than_seconds=offline_after)
            consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            log.warning(
                "device_offline_detector.sweep_failed",
                error=str(exc),
                consecutive=consecutive_failures,
            )

