import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import jwt as pyjwt
import structlog
from fastapi import HTTPException, Request

_audit_log = structlog.get_logger("audit_log")

from .config import SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

# ── C1: Multi-tenant table registry ──────────────────────────────────────────
# Tables that hold per-tenant data. Every service-key query on these tables
# MUST include tenant_id=eq.<id> to prevent cross-tenant data leakage.
# Add a table here when you create a migration that adds a tenant_id column.
MULTI_TENANT_TABLES: frozenset[str] = frozenset({
    "app_users",
    "devices",
    "documents",
    "activated_models",
    "workflows",
    "training_jobs",
    "audit_logs",
    "auth_audit",
    "agent_pipelines",
    "agent_schedules",
    "chat_conversations",
    "chat_messages",
    "decision_reviews",
    "device_analytics",
    "device_licenses",
    "device_models",
    "policy_comparisons",
    "pod_activation_requests",
    "training_feedback",
    "visual_workflows",
    "workflow_runs",
    "acord_extraction_runs",
    "acord_extract_jobs",
    "acord_extraction_feedback",
})


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

    # Fast path: verify JWT signature locally — zero network calls.
    # Falls back to Supabase HTTP call if JWT_SECRET is not configured.
    if SUPABASE_JWT_SECRET:
        try:
            payload = pyjwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return {
                "id": user_id,
                "email": payload.get("email", ""),
                "app_metadata": payload.get("app_metadata", {}),
                "user_metadata": payload.get("user_metadata", {}),
                "role": payload.get("role", "authenticated"),
            }
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Unauthorized")
        except pyjwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Slow path: SUPABASE_JWT_SECRET not set — call Supabase auth server.
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

    # Fallback 1: user metadata can carry tenant_id in some environments.
    if tenant_id is None:
        try:
            md = user.get("user_metadata") if isinstance(user, dict) else None
            if isinstance(md, dict):
                md_tid = md.get("tenant_id") or md.get("tenantId")
                if md_tid:
                    tenant_id = str(md_tid)
        except Exception:
            tenant_id = tenant_id

    # Fallback: some global_admin/admin accounts can have tenant_id NULL in app_users.
    # Derive tenant_id from the JWT claim if present so tenant-scoped routes remain safe.
    if tenant_id is None and authorization and authorization.lower().startswith("bearer "):
        try:
            token = authorization.split(" ", 1)[1]
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                payload_raw = __import__("base64").urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
                payload = json.loads(payload_raw)
                claim_tenant_id = payload.get("tenant_id")
                if claim_tenant_id:
                    tenant_id = str(claim_tenant_id)
        except Exception:
            tenant_id = tenant_id

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


# ── C1: Tenant-scoped PostgREST helpers ──────────────────────────────────────
# These wrappers enforce tenant_id on every query so a missing filter can never
# silently return cross-tenant rows even when the service role key is used.

def _assert_tenant_id(tenant_id: Optional[str], table: str) -> str:
    """Raise ValueError at call time if tenant_id is missing for a multi-tenant table."""
    if table in MULTI_TENANT_TABLES and not tenant_id:
        raise ValueError(
            f"tenant_scoped_get/insert/patch called on multi-tenant table '{table}' "
            "without a tenant_id. Pass tenant_id from get_user_context() — never derive "
            "it from user input."
        )
    return tenant_id or ""


async def tenant_scoped_get(
    table: str,
    query: str,
    tenant_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    postgrest_get with mandatory tenant_id filter.
    Appends &tenant_id=eq.<id> automatically — callers must NOT add it themselves.
    """
    _assert_tenant_id(tenant_id, table)
    scoped_query = f"{query}&tenant_id=eq.{quote(tenant_id, safe='')}"
    return await postgrest_get(table, scoped_query)


async def tenant_scoped_insert(
    table: str,
    payload: Dict[str, Any],
    tenant_id: Optional[str],
) -> List[Dict[str, Any]]:
    """
    postgrest_insert with mandatory tenant_id injected into the payload.
    Prevents accidentally creating rows that belong to no tenant.
    """
    _assert_tenant_id(tenant_id, table)
    scoped_payload = {**payload, "tenant_id": tenant_id}
    return await postgrest_insert(table, scoped_payload)


async def tenant_scoped_patch(
    table: str,
    query: str,
    payload: Dict[str, Any],
    tenant_id: Optional[str],
) -> None:
    """
    postgrest_patch with mandatory tenant_id filter.
    Prevents a patch from accidentally touching another tenant's rows.
    """
    _assert_tenant_id(tenant_id, table)
    scoped_query = f"{query}&tenant_id=eq.{quote(tenant_id, safe='')}"
    return await postgrest_patch(table, scoped_query, payload)


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

        tenant_id_value: Optional[str] = None
        if user_id:
            try:
                prof = await postgrest_get(
                    "app_users",
                    f"select=tenant_id&user_id=eq.{quote(str(user_id), safe='')}&limit=1",
                )
                if prof:
                    tid = prof[0].get("tenant_id")
                    if tid is not None:
                        tenant_id_value = str(tid)
            except Exception:
                tenant_id_value = None

        row: Dict[str, Any] = {
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
        }
        if tenant_id_value:
            row["tenant_id"] = tenant_id_value

        await postgrest_insert("audit_logs", row)
    except Exception as exc:  # noqa: BLE001 — never block callers; log for ops visibility
        _audit_log.warning(
            "audit_logs_insert_failed",
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            error=str(exc),
        )


async def insert_auth_audit_row(
    user_id: str,
    email: str,
    role: str,
    event: str,
    action_code: str,
    outcome_code: int,
    resource_type: str,
    resource_id: Optional[str],
) -> None:
    """Insert auth_audit via service role. Hash matches frontend ``auditHash.ts`` (no email in hash)."""
    try:
        created_at = datetime.now(timezone.utc).isoformat()
        oc: Any = outcome_code if isinstance(outcome_code, int) else ""
        hash_payload = {
            "user_id": user_id,
            "role": role or "user",
            "event": event,
            "action_code": action_code or "",
            "outcome_code": oc,
            "resource_type": resource_type or "",
            "resource_id": resource_id or "",
            "created_at": created_at,
        }
        serialized = json.dumps(hash_payload, separators=(",", ":"), ensure_ascii=False)
        integrity_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        await postgrest_insert(
            "auth_audit",
            {
                "user_id": user_id,
                "email": email or "",
                "role": role or "user",
                "event": event,
                "action_code": action_code,
                "outcome_code": outcome_code,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "created_at": created_at,
                "integrity_hash": integrity_hash,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _audit_log.warning(
            "auth_audit_insert_failed",
            event=event,
            user_id=user_id,
            error=str(exc),
        )


async def admin_list_users() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=service_headers(json_body=False),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    return resp.json().get("users", [])
