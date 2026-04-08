import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib.parse import quote

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import (
    WEBHOOK_MAX_ATTEMPTS,
    WEBHOOK_RETRY_BASE_SECONDS,
    WEBHOOK_RETRY_MAX_SECONDS,
    WEBHOOK_SECRET_ENCRYPTION_KEY,
)
from app.core.supabase import postgrest_get, postgrest_insert, postgrest_patch

log = structlog.get_logger("webhooks")

# Canonical event names (subscribe in webhook registration UI / API).
WEBHOOK_EVENT_DEVICE_ONLINE = "device.online"
WEBHOOK_EVENT_MODEL_DEPLOYED = "model.deployed"
WEBHOOK_EVENT_INFERENCE_COMPLETE = "inference.complete"

_device_online_last_emit_monotonic: dict[str, float] = {}


def _device_online_min_interval_sec() -> float:
    try:
        return max(30.0, float(os.getenv("WEBHOOK_DEVICE_ONLINE_MIN_SECONDS", "300")))
    except ValueError:
        return 300.0


async def resolve_tenant_id_for_device(device_id: str) -> Optional[str]:
    rows = await postgrest_get(
        "devices",
        f"select=tenant_id,registered_by&id=eq.{quote(device_id, safe='')}&limit=1",
    )
    if not rows:
        return None
    r = rows[0]
    tid = r.get("tenant_id")
    if tid is not None and str(tid).strip():
        return str(tid)
    rb = r.get("registered_by")
    if rb:
        ur = await postgrest_get(
            "app_users",
            f"select=tenant_id&user_id=eq.{quote(str(rb), safe='')}&limit=1",
        )
        if ur and ur[0].get("tenant_id") is not None and str(ur[0].get("tenant_id")).strip():
            return str(ur[0]["tenant_id"])
    return None


async def resolve_tenant_id_for_user(user_id: str) -> Optional[str]:
    rows = await postgrest_get(
        "app_users",
        f"select=tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    if not rows or rows[0].get("tenant_id") is None:
        return None
    tid = rows[0].get("tenant_id")
    return str(tid).strip() if tid else None


async def try_emit_webhook_event(
    tenant_id: Optional[str],
    event_type: str,
    payload: dict[str, Any],
) -> None:
    if not tenant_id or not str(tenant_id).strip():
        return
    try:
        await emit_event(str(tenant_id).strip(), event_type, payload)
        log.info("webhooks.event_enqueued", event_type=event_type, tenant_id=str(tenant_id))
    except Exception as exc:  # noqa: BLE001
        log.warning("webhooks.emit_failed", event_type=event_type, error=str(exc))


async def try_emit_device_online(device_id: str, *, force: bool = False) -> None:
    try:
        tenant_id = await resolve_tenant_id_for_device(device_id)
    except Exception as exc:  # noqa: BLE001
        # Webhooks are best-effort and must never break primary flows like device registration/heartbeat.
        log.warning("webhooks.resolve_tenant_failed", device_id=device_id, error=str(exc))
        return
    if not tenant_id:
        return
    if not force:
        now = time.monotonic()
        last = _device_online_last_emit_monotonic.get(device_id, 0.0)
        if now - last < _device_online_min_interval_sec():
            return
        _device_online_last_emit_monotonic[device_id] = now
    else:
        _device_online_last_emit_monotonic[device_id] = time.monotonic()
    await try_emit_webhook_event(
        tenant_id,
        WEBHOOK_EVENT_DEVICE_ONLINE,
        {"device_id": device_id},
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_encryption_key() -> Fernet:
    raw = WEBHOOK_SECRET_ENCRYPTION_KEY.strip()
    if not raw:
        raise RuntimeError("WEBHOOK_SECRET_ENCRYPTION_KEY is not set")
    # Accept either a valid Fernet key or raw bytes that we derive into one.
    try:
        # Fernet expects urlsafe base64-encoded 32-byte key.
        return Fernet(raw.encode("utf-8"))
    except Exception:
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
        return Fernet(key)


def generate_webhook_secret() -> str:
    # Similar entropy to typical webhook providers.
    return secrets.token_urlsafe(32)


def hash_webhook_secret(secret_value: str) -> str:
    return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()


def encrypt_secret(secret_value: str) -> str:
    f = _require_encryption_key()
    token = f.encrypt(secret_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    f = _require_encryption_key()
    try:
        raw = f.decrypt(encrypted_secret.encode("utf-8"))
        return raw.decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Webhook secret decrypt failed") from exc


def sign_payload_hmac_sha256(secret_value: str, body_bytes: bytes) -> str:
    digest = hmac.new(secret_value.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def emit_event(tenant_id: str, event_type: str, payload: dict[str, Any]) -> str:
    """Insert a durable event row and enqueue deliveries for matching webhooks."""
    event_rows = await postgrest_insert(
        "webhook_events",
        {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "payload": payload,
        },
    )
    event_id = str(event_rows[0]["id"]) if event_rows else ""
    if not event_id:
        raise RuntimeError("Failed to insert webhook event")

    # Match active webhooks in tenant.
    # "events" empty means "all events".
    hooks = await postgrest_get(
        "webhooks",
        (
            "select=id,events,is_active"
            f"&tenant_id=eq.{quote(tenant_id, safe='')}"
            "&is_active=eq.true"
            "&limit=500"
        ),
    )
    for hook in hooks:
        subscribed = hook.get("events") or []
        if isinstance(subscribed, list) and subscribed and event_type not in subscribed:
            continue
        await postgrest_insert(
            "webhook_deliveries",
            {
                "tenant_id": tenant_id,
                "webhook_id": hook["id"],
                "event_id": event_id,
                "status": "pending",
                "attempt_count": 0,
                "next_attempt_at": _utc_now().isoformat(),
            },
        )
    return event_id


def _backoff_seconds(attempt_number: int) -> float:
    # attempt_number starts at 1 for the first failure.
    base = max(0.1, float(WEBHOOK_RETRY_BASE_SECONDS))
    max_s = max(base, float(WEBHOOK_RETRY_MAX_SECONDS))
    return min(max_s, base * (2 ** max(0, attempt_number - 1)))


async def _fetch_due_deliveries(limit: int = 25) -> list[dict[str, Any]]:
    now_iso = _utc_now().isoformat()
    query = (
        "select=id,tenant_id,webhook_id,event_id,attempt_count,status,next_attempt_at"
        "&status=eq.pending"
        f"&next_attempt_at=lte.{quote(now_iso, safe='')}"
        "&order=next_attempt_at.asc"
        f"&limit={limit}"
    )
    return await postgrest_get("webhook_deliveries", query)


async def _load_webhook(webhook_id: str) -> dict[str, Any]:
    rows = await postgrest_get("webhooks", f"select=*&id=eq.{quote(webhook_id, safe='')}&limit=1")
    if not rows:
        raise RuntimeError("Webhook not found")
    return rows[0]


async def _load_active_secret(tenant_id: str, webhook_id: str) -> dict[str, Any]:
    rows = await postgrest_get(
        "webhook_secrets",
        (
            "select=encrypted_secret,secret_hash"
            f"&tenant_id=eq.{quote(tenant_id, safe='')}"
            f"&webhook_id=eq.{quote(webhook_id, safe='')}"
            "&is_active=eq.true"
            "&order=created_at.desc"
            "&limit=1"
        ),
    )
    if not rows:
        raise RuntimeError("Webhook secret not configured")
    return rows[0]


async def _load_event(event_id: str) -> dict[str, Any]:
    rows = await postgrest_get("webhook_events", f"select=*&id=eq.{quote(event_id, safe='')}&limit=1")
    if not rows:
        raise RuntimeError("Webhook event not found")
    return rows[0]


async def _mark_delivery(delivery_id: str, patch: dict[str, Any]) -> None:
    await postgrest_patch("webhook_deliveries", f"id=eq.{quote(delivery_id, safe='')}", patch)


async def _attempt_delivery(delivery: dict[str, Any]) -> None:
    delivery_id = str(delivery["id"])
    tenant_id = str(delivery["tenant_id"])
    webhook_id = str(delivery["webhook_id"])
    event_id = str(delivery["event_id"])
    attempt_count = int(delivery.get("attempt_count") or 0)

    webhook = await _load_webhook(webhook_id)
    if not webhook.get("is_active", False):
        await _mark_delivery(delivery_id, {"status": "failed", "last_error": "Webhook is inactive"})
        return

    secret_row = await _load_active_secret(tenant_id, webhook_id)
    secret_value = decrypt_secret(str(secret_row["encrypted_secret"]))

    event = await _load_event(event_id)
    event_type = str(event.get("event_type") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}

    body = json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "created_at": event.get("created_at"),
            "data": payload,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    signature = sign_payload_hmac_sha256(secret_value, body)
    timestamp = str(int(_utc_now().timestamp()))

    headers = {
        "Content-Type": "application/json",
        "X-Fideon-Event": event_type,
        "X-Fideon-Delivery-Id": delivery_id,
        "X-Fideon-Timestamp": timestamp,
        # Product / spec name (NeuraPod) — same HMAC value as X-Fideon-Signature.
        "X-Fideon-Signature": signature,
        "X-NeuraPod-Signature": signature,
    }

    await _mark_delivery(
        delivery_id,
        {"last_attempt_at": _utc_now().isoformat()},
    )

    url = str(webhook.get("url") or "").strip()
    if not url:
        await _mark_delivery(delivery_id, {"status": "failed", "last_error": "Webhook URL missing"})
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, content=body, headers=headers)
        if 200 <= resp.status_code < 300:
            await _mark_delivery(
                delivery_id,
                {
                    "status": "delivered",
                    "delivered_at": _utc_now().isoformat(),
                    "response_status": resp.status_code,
                    "response_body": (resp.text or "")[:2000],
                    "last_error": None,
                },
            )
            return

        # Non-2xx => retry
        next_attempt = attempt_count + 1
        if next_attempt >= int(WEBHOOK_MAX_ATTEMPTS):
            await _mark_delivery(
                delivery_id,
                {
                    "status": "dead_letter",
                    "attempt_count": next_attempt,
                    "response_status": resp.status_code,
                    "response_body": (resp.text or "")[:2000],
                    "last_error": f"Non-2xx response: {resp.status_code}",
                    "next_attempt_at": (_utc_now() + timedelta(seconds=_backoff_seconds(next_attempt))).isoformat(),
                },
            )
            return
        await _mark_delivery(
            delivery_id,
            {
                "status": "pending",
                "attempt_count": next_attempt,
                "response_status": resp.status_code,
                "response_body": (resp.text or "")[:2000],
                "last_error": f"Non-2xx response: {resp.status_code}",
                "next_attempt_at": (_utc_now() + timedelta(seconds=_backoff_seconds(next_attempt))).isoformat(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        next_attempt = attempt_count + 1
        patch: dict[str, Any] = {
            "attempt_count": next_attempt,
            "last_error": str(exc)[:2000],
            "next_attempt_at": (_utc_now() + timedelta(seconds=_backoff_seconds(next_attempt))).isoformat(),
        }
        if next_attempt >= int(WEBHOOK_MAX_ATTEMPTS):
            patch["status"] = "dead_letter"
        else:
            patch["status"] = "pending"
        await _mark_delivery(delivery_id, patch)


async def delivery_worker_loop(poll_seconds: float = 2.0) -> None:
    """Background loop that delivers pending webhook deliveries."""
    consecutive_failures = 0
    while True:
        await asyncio.sleep(poll_seconds)
        try:
            due = await _fetch_due_deliveries(limit=25)
            if not due:
                consecutive_failures = 0
                continue
            for d in due:
                await _attempt_delivery(d)
            consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            log.error("webhooks.worker_failed", error=str(exc), consecutive=consecutive_failures)

