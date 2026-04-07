"""
Model registry: insurance-task benchmarks (BLEU, F1, latency) and optional MLflow sync.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import quote

import httpx
import structlog
from fastapi import APIRouter, Header, HTTPException

from app.core.config import MLFLOW_API_TOKEN, MLFLOW_TRACKING_URI
from app.core.supabase import get_user_context, postgrest_get, postgrest_insert, postgrest_patch, verify_admin

log = structlog.get_logger("model_registry")
router = APIRouter()

TASK_LABELS: dict[str, str] = {
    "document_qa": "Document Q&A",
    "policy_comparison": "Policy comparison",
    "acord_extraction": "ACORD extraction",
}


def _mlflow_headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if MLFLOW_API_TOKEN:
        h["Authorization"] = f"Bearer {MLFLOW_API_TOKEN}"
    return h


def _latest_metrics(metrics: list[dict[str, Any]]) -> dict[str, float]:
    """MLflow returns repeated metric keys; keep the row with highest step per key."""
    best: dict[str, tuple[float, int]] = {}
    for m in metrics or []:
        key = str(m.get("key") or "").strip().lower()
        if not key:
            continue
        try:
            val = float(m.get("value"))
        except (TypeError, ValueError):
            continue
        step = int(m.get("step") or 0)
        prev = best.get(key)
        if prev is None or step >= prev[1]:
            best[key] = (val, step)
    return {k: v[0] for k, v in best.items()}


def _metric_float(m: dict[str, float], *names: str) -> Optional[float]:
    for n in names:
        k = n.lower()
        if k in m:
            return float(m[k])
    return None


def _tag_map(tags: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in tags or []:
        k = str(t.get("key") or "").strip()
        v = t.get("value")
        if k:
            out[k] = str(v) if v is not None else ""
    return out


async def _mlflow_list_experiments(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    r = await client.get(f"{base}/api/2.0/mlflow/experiments/list", headers=_mlflow_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"MLflow experiments list failed: {r.text[:500]}")
    data = r.json()
    return list(data.get("experiments") or [])


async def _mlflow_search_runs(
    client: httpx.AsyncClient,
    base: str,
    experiment_ids: list[str],
    max_results: int = 200,
) -> list[dict[str, Any]]:
    r = await client.post(
        f"{base}/api/2.0/mlflow/runs/search",
        headers=_mlflow_headers(),
        content=json.dumps(
            {
                "experiment_ids": experiment_ids,
                "max_results": max_results,
                "run_view_type": "ACTIVE_ONLY",
            }
        ),
    )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"MLflow runs search failed: {r.text[:500]}")
    data = r.json()
    return list(data.get("runs") or [])


def _registry_scope_filter(tenant_id: Optional[str]) -> str:
    """PostgREST filter: global rows (tenant_id is null) OR this tenant."""
    if not tenant_id:
        return "tenant_id=is.null"
    tid = quote(str(tenant_id), safe="")
    return f"or=(tenant_id.is.null,tenant_id.eq.{tid})"


@router.get("/api/v1/model-registry")
async def list_model_registry(
    task_key: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """List registry rows visible to the admin (global catalog + own tenant)."""
    await verify_admin(authorization)
    ctx = await get_user_context(authorization)
    tenant_id = ctx.get("tenant_id")
    scope = _registry_scope_filter(str(tenant_id) if tenant_id else None)
    parts: list[str] = ["select=*", scope]
    if task_key:
        tk = quote(str(task_key).strip(), safe="")
        parts.append(f"task_key=eq.{tk}")
    parts.extend(["order=task_key.asc,base_model.asc", "limit=500"])
    q = "&".join(parts)
    rows = await postgrest_get("model_registry", q)
    return {"models": rows}


@router.post("/api/v1/model-registry/recompute-best")
async def recompute_best_models(authorization: Optional[str] = Header(default=None)):
    """Set is_best_for_task per task_key using average of BLEU and F1 (latency tie-breaker: lower is better)."""
    await verify_admin(authorization)
    ctx = await get_user_context(authorization)
    tenant_id = ctx.get("tenant_id")
    scope = _registry_scope_filter(str(tenant_id) if tenant_id else None)
    rows = await postgrest_get(
        "model_registry",
        f"select=id,task_key,tenant_id,bleu_score,f1_score,latency_ms&{scope}&limit=500",
    )
    # Best model per (task_key, tenant_id) — global seeds (tenant_id NULL) are separate from tenant rows.
    by_bucket: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows or []:
        tk = str(r.get("task_key") or "")
        if not tk:
            continue
        tid = r.get("tenant_id")
        bucket = (tk, str(tid) if tid is not None else "__global__")
        by_bucket.setdefault(bucket, []).append(r)

    def score_row(r: dict[str, Any]) -> tuple[float, float]:
        b = r.get("bleu_score")
        f = r.get("f1_score")
        lat = r.get("latency_ms")
        bleu = float(b) if b is not None else 0.0
        f1 = float(f) if f is not None else 0.0
        primary = (bleu + f1) / 2.0 if (b is not None or f is not None) else 0.0
        latency = float(lat) if lat is not None else 1e9
        return (primary, -latency)

    best_ids: set[str] = set()
    for _bucket, group in by_bucket.items():
        if not group:
            continue
        best = max(group, key=score_row)
        bid = best.get("id")
        if bid:
            best_ids.add(str(bid))

    for r in rows or []:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        want = rid in best_ids
        await postgrest_patch("model_registry", f"id=eq.{quote(rid, safe='')}", {"is_best_for_task": want})

    log.info("model_registry.recompute_best", buckets=len(by_bucket))
    return {"success": True, "buckets_updated": len(by_bucket)}


@router.post("/api/v1/model-registry/sync-mlflow")
async def sync_from_mlflow(
    authorization: Optional[str] = Header(default=None),
    max_experiments: int = 25,
    max_runs_per_batch: int = 200,
):
    """
    Pull runs from MLflow Tracking REST API and upsert into model_registry.

    Expected run tags (any of):
      - task_key or task
      - base_model or model_family
    Expected metrics (case-insensitive):
      - bleu / BLEU
      - f1 / f1_score / F1
      - latency_ms / latency / infer_latency_ms
    """
    await verify_admin(authorization)
    if not MLFLOW_TRACKING_URI:
        raise HTTPException(
            status_code=503,
            detail="MLFLOW_TRACKING_URI is not configured on the API server",
        )

    ctx = await get_user_context(authorization)
    tenant_id = ctx.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to sync MLflow runs")

    base = MLFLOW_TRACKING_URI.rstrip("/")
    inserted = 0
    updated = 0

    async with httpx.AsyncClient(timeout=120) as client:
        experiments = await _mlflow_list_experiments(client, base)
        experiments = sorted(experiments, key=lambda e: str(e.get("name") or ""))[: max(1, max_experiments)]
        exp_ids = [str(e["experiment_id"]) for e in experiments if e.get("experiment_id") is not None]
        if not exp_ids:
            return {"success": True, "inserted": 0, "updated": 0, "message": "No MLflow experiments found"}

        runs = await _mlflow_search_runs(client, base, exp_ids, max_results=max_runs_per_batch)

        for run in runs:
            info = run.get("info") or {}
            data = run.get("data") or {}
            run_id = str(info.get("run_id") or "").strip()
            if not run_id:
                continue
            exp_id = str(info.get("experiment_id") or "").strip()
            tags = _tag_map(data.get("tags") or [])
            task_key = (
                tags.get("task_key")
                or tags.get("task")
                or tags.get("insurance_task")
                or "document_qa"
            ).strip()
            base_model = (tags.get("base_model") or tags.get("model_family") or tags.get("model") or "unknown").strip()
            display_name = (tags.get("display_name") or tags.get("mlflow.runName") or base_model).strip()

            m = _latest_metrics(data.get("metrics") or [])
            bleu = _metric_float(m, "bleu", "bleu_score", "corpus_bleu")
            f1 = _metric_float(m, "f1", "f1_score", "token_f1", "micro_f1")
            lat = _metric_float(m, "latency_ms", "latency", "infer_latency_ms", "avg_latency_ms")

            task_label = TASK_LABELS.get(task_key, task_key.replace("_", " ").title())
            meta = {
                "mlflow_run_name": info.get("run_name"),
                "synced_tags": tags,
            }

            existing = await postgrest_get(
                "model_registry",
                f"select=id&mlflow_run_id=eq.{quote(run_id, safe='')}&limit=1",
            )
            payload: dict[str, Any] = {
                "tenant_id": str(tenant_id),
                "task_key": task_key,
                "task_label": task_label,
                "base_model": base_model,
                "display_name": display_name or base_model,
                "bleu_score": bleu,
                "f1_score": f1,
                "latency_ms": lat,
                "mlflow_run_id": run_id,
                "mlflow_experiment_id": exp_id or None,
                "source": "mlflow",
                "metadata": meta,
                "is_best_for_task": False,
            }

            if existing:
                await postgrest_patch(
                    "model_registry",
                    f"id=eq.{quote(str(existing[0]['id']), safe='')}",
                    {
                        "task_key": payload["task_key"],
                        "task_label": payload["task_label"],
                        "base_model": payload["base_model"],
                        "display_name": payload["display_name"],
                        "bleu_score": bleu,
                        "f1_score": f1,
                        "latency_ms": lat,
                        "mlflow_experiment_id": payload["mlflow_experiment_id"],
                        "source": "mlflow",
                        "metadata": meta,
                    },
                )
                updated += 1
            else:
                await postgrest_insert("model_registry", payload)
                inserted += 1

    # Recompute best including new MLflow rows for this tenant's tasks
    await recompute_best_models(authorization=authorization)

    log.info("model_registry.mlflow_sync", inserted=inserted, updated=updated)
    return {
        "success": True,
        "inserted": inserted,
        "updated": updated,
        "experiments_scanned": len(exp_ids),
        "runs_fetched": len(runs),
    }
