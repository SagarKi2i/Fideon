import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request

from .config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def service_headers(json_body: bool = True) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


async def verify_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return resp.json()


async def verify_admin(authorization: Optional[str]) -> Dict[str, Any]:
    """Verify the caller is an authenticated admin or global_admin.

    Raises 401 if the token is invalid, 403 if the user lacks admin privileges.
    Returns the Supabase user dict on success.
    """
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rows = await postgrest_get(
        "user_roles",
        f"select=role&user_id=eq.{quote(user_id, safe='')}&role=in.(admin,global_admin)&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


async def get_user_context(authorization: Optional[str]) -> Dict[str, Any]:
    """Return authenticated user context (id, role, tenant_id).

    This helper centralizes tenant-aware authorization checks for route handlers.
    """
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role_rows = await postgrest_get(
        "user_roles",
        f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    role = role_rows[0].get("role") if role_rows else None

    profile_rows = await postgrest_get(
        "app_users",
        f"select=tenant_id&user_id=eq.{quote(user_id, safe='')}&limit=1",
    )
    tenant_id = profile_rows[0].get("tenant_id") if profile_rows else None

    return {
        "user": user,
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
    }


async def postgrest_get(table: str, query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json()


async def postgrest_insert(table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    headers = service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json()


async def postgrest_patch(table: str, query: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(),
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)


async def postgrest_delete(table: str, query: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)


async def get_device_by_token(device_token: str) -> Dict[str, Any]:
    token_hash = hashlib.sha256(device_token.encode("utf-8")).hexdigest()
    encoded_hash = quote(token_hash, safe="")
    rows = await postgrest_get("devices", f"select=*&token_hash=eq.{encoded_hash}&limit=1")
    if not rows:
        # Backward compatibility for environments where token_hash is not yet present.
        encoded = quote(device_token, safe="")
        rows = await postgrest_get("devices", f"select=*&device_token=eq.{encoded}&limit=1")
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid device token")
    device = rows[0]
    if not device.get("is_active", False):
        raise HTTPException(status_code=403, detail="Device is deactivated")
    return device


# Fields that must NEVER appear in previous_value / new_value JSONB.
# This is a safety net — callers should only pass non-PII fields
# (role names, status strings, model IDs, UUIDs) to begin with.
_AUDIT_PII_FIELDS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "authorization",
    "email", "ssn", "social_security", "credit_card", "card_number", "cvv",
    "dob", "date_of_birth", "birth_date", "full_name", "first_name",
    "last_name", "mobile", "phone", "phone_number", "address",
})


def _scrub_audit_value(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Remove known PII/PHA field names from a change-value dict before storage or hashing.

    Only top-level keys are scrubbed — these dicts must be shallow by design
    (role names, status strings, model IDs). Returns None unchanged.
    """
    if value is None:
        return None
    return {
        k: ("[REDACTED]" if k.lower() in _AUDIT_PII_FIELDS else v)
        for k, v in value.items()
    }


async def insert_audit_log(
    request: Request,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    previous_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    # ── AI / SHAP explainability fields (optional) ────────────
    shap_values: Optional[Dict[str, float]] = None,
    model_id: Optional[str] = None,
    prediction: Optional[Dict[str, Any]] = None,
    reasoning: Optional[str] = None,
) -> None:
    """Insert an immutable audit row into audit_logs.

    Captures ip_address, user_agent, previous_value, new_value, and a
    SHA-256 integrity_hash covering all non-PII fields for EU AI Act /
    SOC2 / NAIC compliance.

    previous_value / new_value must contain ONLY non-PII fields (role names,
    status strings, model IDs, UUIDs). Never pass emails, names, or passwords.
    Both are PII-scrubbed before storage and included in the integrity hash so
    any post-write tampering is detectable.

    AI decisions can be recorded with full SHAP explainability:
      shap_values — dict mapping feature names to their SHAP float values.
      model_id    — identifier of the model that produced the decision.
      prediction  — model output / decision outcome as a dict.
      reasoning   — human-readable explanation (auto-generated via
                    generate_shap_reasoning() in logger/__init__.py if not
                    supplied directly).

    All SHAP / AI fields are included in the integrity_hash so any
    post-write tampering with the explanation is detectable.
    The database trigger (compute_audit_chain_hash) appends a chain_hash
    linking this row cryptographically to the previous ledger entry.

    Failures are silently swallowed so auditing never blocks the main request.
    """
    try:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        created_at = datetime.now(timezone.utc).isoformat()

        # Scrub PII/PHA from change values before hashing or storing.
        safe_previous = _scrub_audit_value(previous_value)
        safe_new = _scrub_audit_value(new_value)

        # SHA-256 integrity hash covers all non-PII structured fields,
        # including SHAP/AI decision data so tampering with the explanation
        # invalidates the hash.  chain_hash (ledger linkage) is computed by
        # the DB trigger after insert and is therefore NOT included here.
        hash_payload = json.dumps({
            "user_id": user_id or "",
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id or "",
            "previous_value": json.dumps(safe_previous, sort_keys=True) if safe_previous else "",
            "new_value": json.dumps(safe_new, sort_keys=True) if safe_new else "",
            "model_id": model_id or "",
            "prediction": json.dumps(prediction, sort_keys=True) if prediction else "",
            "shap_values": json.dumps(shap_values, sort_keys=True) if shap_values else "",
            "reasoning": reasoning or "",
            "created_at": created_at,
        }, sort_keys=True)
        integrity_hash = hashlib.sha256(hash_payload.encode()).hexdigest()

        await postgrest_insert("audit_logs", {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "previous_value": safe_previous,
            "new_value": safe_new,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": created_at,
            "integrity_hash": integrity_hash,
            # AI / SHAP fields — None values are omitted by PostgREST
            "shap_values": shap_values,
            "model_id": model_id,
            "prediction": prediction,
            "reasoning": reasoning,
        })
    except Exception:
        pass  # Audit failure must never block the main request path


async def admin_list_users() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json().get("users", [])
