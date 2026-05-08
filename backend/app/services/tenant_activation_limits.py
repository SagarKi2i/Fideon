"""Tenant plan limits for distinct activated marketplace models (pods)."""

from typing import Optional, Set
from urllib.parse import quote

from fastapi import HTTPException

from app.core.supabase import postgrest_get

# Matches Starter (3) / Professional (8) / Enterprise (unlimited) from plan_limits RPC.
ACTIVE_MODEL_LIMIT_DETAIL = "Please upgrade your plan to add more active models."


async def list_tenant_user_ids(tenant_id: str) -> list[str]:
    rows = await postgrest_get(
        "app_users",
        f"select=user_id&tenant_id=eq.{quote(str(tenant_id), safe='')}",
    )
    return [str(r["user_id"]) for r in rows if r.get("user_id")]


async def distinct_tenant_activated_model_ids(tenant_id: str) -> Set[str]:
    """Distinct model_id values activated for any user in the tenant."""
    user_ids = await list_tenant_user_ids(tenant_id)
    if not user_ids:
        return set()
    encoded = ",".join(quote(uid, safe="") for uid in user_ids)
    rows = await postgrest_get(
        "activated_models",
        f"select=model_id&user_id=in.({encoded})",
    )
    return {str(r["model_id"]) for r in rows if r.get("model_id")}


async def get_tenant_max_active_models(tenant_id: str) -> Optional[int]:
    """None means unlimited (e.g. Enterprise)."""
    rows = await postgrest_get(
        "tenants",
        f"select=max_active_models&id=eq.{quote(str(tenant_id), safe='')}&limit=1",
    )
    if not rows:
        return None
    raw = rows[0].get("max_active_models")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def tenant_may_add_distinct_model(
    *,
    max_active_models: Optional[int],
    current_distinct_ids: Set[str],
    model_id: str,
) -> bool:
    if max_active_models is None:
        return True
    mid = (model_id or "").strip()
    if not mid:
        return True
    if mid in current_distinct_ids:
        return True
    return len(current_distinct_ids) < max_active_models


async def assert_tenant_may_add_distinct_model(tenant_id: str, model_id: str) -> None:
    """Raise HTTP 403 when the tenant cannot add another distinct model under their plan."""
    mid = (model_id or "").strip()
    if not mid:
        return
    max_m = await get_tenant_max_active_models(tenant_id)
    if max_m is None:
        return
    distinct = await distinct_tenant_activated_model_ids(tenant_id)
    if tenant_may_add_distinct_model(
        max_active_models=max_m,
        current_distinct_ids=distinct,
        model_id=mid,
    ):
        return
    raise HTTPException(status_code=403, detail=ACTIVE_MODEL_LIMIT_DETAIL)
