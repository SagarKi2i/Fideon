import logging
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, Query, UploadFile

from app.core.supabase import postgrest_get, postgrest_insert, postgrest_patch, verify_user
from app.schemas.pod_workflow import (
    PodAdminReviewRequest,
    PodBatchReviewRequest,
    PodExtractResponse,
    PodReExtractRequest,
    PodSubmitRequest,
)
from app.services.pod_extraction import (
    extract_and_prepare_pod_reextract_from_raw_text,
    extract_and_prepare_pod_run,
)
from app.services.pod_training import create_job_row, spawn_job_runner

router = APIRouter(prefix="/api/pods", tags=["pods"])
logger = logging.getLogger("fideon.pods")


POD_CONFIDENCE_THRESHOLD = float(os.getenv("POD_CONFIDENCE_THRESHOLD", os.getenv("ACORD_CONFIDENCE_THRESHOLD", "0.85")))

TABLE_RUNS = "pod_extraction_runs"
TABLE_FEEDBACK = "pod_extraction_feedback"
TABLE_QUEUE = "pod_admin_queue"
TABLE_JOBS = "pod_training_jobs"
TABLE_EVAL_RESULTS = "pod_eval_results"


def _clamp01(v: float) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return 0.0


def _evaluate_confidence_and_feedback(
    *,
    base_confidence: float,
    run_status: str,
    original_json: dict,
    edited_json: dict,
    feedback_rows: list[dict],
) -> dict:
    status = str(run_status or "").strip().lower()
    latest_thumbs = None
    latest_actor = None
    corrections_count = 0
    for row in feedback_rows or []:
        if latest_thumbs is None and "thumbs_up" in row:
            latest_thumbs = row.get("thumbs_up")
            latest_actor = row.get("actor_role")
        if row.get("corrected_json") is not None:
            corrections_count += 1

    has_user_or_admin_edits = bool(corrections_count > 0 or (original_json or {}) != (edited_json or {}))
    adjustment = 0.0
    reasons: list[str] = []
    if latest_thumbs is True:
        adjustment += 0.05
        reasons.append("latest_feedback_positive")
    elif latest_thumbs is False:
        adjustment -= 0.08
        reasons.append("latest_feedback_negative")
    if has_user_or_admin_edits:
        adjustment -= 0.10
        reasons.append("json_was_manually_corrected")
    if status == "approved":
        adjustment += 0.04
        reasons.append("admin_approved")
    elif status in {"rejected", "needs_admin_review"}:
        adjustment -= 0.06
        reasons.append("requires_or_failed_admin_review")

    calibrated = _clamp01(float(base_confidence or 0.0) + adjustment)
    return {
        "base_confidence": _clamp01(base_confidence),
        "calibrated_confidence": calibrated,
        "adjustment": round(adjustment, 4),
        "reasons": reasons,
        "feedback_signals": {
            "total_feedback_entries": len(feedback_rows or []),
            "corrections_count": corrections_count,
            "has_manual_edits": has_user_or_admin_edits,
            "latest_thumbs_up": latest_thumbs,
            "latest_feedback_actor_role": latest_actor,
        },
    }


def _eval_weighted(rows_by_set: dict[str, dict], metric_key: str, sets: list[str]) -> Optional[float]:
    total_n = 0.0
    weighted = 0.0
    for s in sets:
        row = rows_by_set.get(s) or {}
        val = row.get(metric_key)
        if val is None:
            continue
        m = row.get("metrics_json") or {}
        n = float((m.get("n") if isinstance(m, dict) else 0) or 0)
        if n <= 0:
            continue
        total_n += n
        weighted += float(val) * n
    if total_n <= 0:
        return None
    return weighted / total_n


def _quality_gate_snapshot_from_eval_rows(eval_rows: list[dict]) -> dict:
    by_set: dict[str, dict] = {str(r.get("eval_set") or ""): r for r in (eval_rows or [])}
    seen_key = "seen"
    para_key = "paraphrased"
    oos_key = "oos"

    json_valid = _eval_weighted(by_set, "exact_match", [seen_key, para_key])
    json_exact = _eval_weighted(by_set, "exact_match", [seen_key, para_key])
    json_recall = None
    json_extra = None
    oos_hall = _eval_weighted(by_set, "hallucination_rate", [oos_key])

    def _weighted_from_metrics_json(metric_name: str) -> Optional[float]:
        total_n = 0.0
        weighted = 0.0
        for s in (seen_key, para_key):
            row = by_set.get(s) or {}
            m = row.get("metrics_json") or {}
            if not isinstance(m, dict):
                continue
            val = m.get(metric_name)
            n = float(m.get("n") or 0)
            if val is None or n <= 0:
                continue
            total_n += n
            weighted += float(val) * n
        if total_n <= 0:
            return None
        return weighted / total_n

    json_valid_m = _weighted_from_metrics_json("json_valid_rate")
    json_exact_m = _weighted_from_metrics_json("json_exact_match")
    json_recall_m = _weighted_from_metrics_json("json_field_recall")
    json_extra_m = _weighted_from_metrics_json("json_extra_field_rate")
    if json_valid_m is not None:
        json_valid = json_valid_m
    if json_exact_m is not None:
        json_exact = json_exact_m
    if json_recall_m is not None:
        json_recall = json_recall_m
    if json_extra_m is not None:
        json_extra = json_extra_m

    min_json_valid = float(os.getenv("FT_QG_MIN_JSON_VALID_RATE", "0.99"))
    min_json_exact = float(os.getenv("FT_QG_MIN_JSON_EXACT_MATCH", "0.90"))
    min_field_recall = float(os.getenv("FT_QG_MIN_JSON_FIELD_RECALL", "0.95"))
    max_extra_field = float(os.getenv("FT_QG_MAX_JSON_EXTRA_FIELD_RATE", "0.02"))
    max_oos_halluc = float(os.getenv("FT_QG_MAX_OOS_HALLUCINATION_RATE", "0.05"))

    checks: list[dict] = []

    def _check(name: str, val: Optional[float], op: str, th: float) -> bool:
        if val is None:
            checks.append({"metric": name, "value": None, "threshold": th, "operator": op, "ok": False})
            return False
        ok = (val >= th) if op == ">=" else (val <= th)
        checks.append({"metric": name, "value": val, "threshold": th, "operator": op, "ok": ok})
        return ok

    ok_all = True
    ok_all &= _check("json_valid_rate", json_valid, ">=", min_json_valid)
    ok_all &= _check("json_exact_match", json_exact, ">=", min_json_exact)
    ok_all &= _check("json_field_recall", json_recall, ">=", min_field_recall)
    ok_all &= _check("json_extra_field_rate", json_extra, "<=", max_extra_field)
    ok_all &= _check("oos_hallucination_rate", oos_hall, "<=", max_oos_halluc)

    return {"pass": bool(ok_all), "checks": checks}


async def _latest_corrected_json_for_run(*, pod_id: str, run_id: str) -> Optional[dict]:
    rows = await postgrest_get(
        TABLE_FEEDBACK,
        (
            "select=corrected_json,created_at"
            f"&pod_id=eq.{quote(pod_id, safe='')}"
            f"&run_id=eq.{quote(run_id, safe='')}"
            "&order=created_at.desc&limit=50"
        ),
    )
    for row in rows or []:
        corrected = row.get("corrected_json")
        if isinstance(corrected, dict):
            return corrected
    return None


def _confidence_threshold() -> float:
    try:
        return float(os.getenv("POD_CONFIDENCE_THRESHOLD", str(POD_CONFIDENCE_THRESHOLD)))
    except Exception:
        return 0.85


async def _require_admin(authorization: str | None) -> dict:
    user = await verify_user(authorization)
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    rows = await postgrest_get("user_roles", f"select=role&user_id=eq.{quote(user['id'], safe='')}&limit=1")
    role = rows[0].get("role") if rows else None
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _ensure_run_access(*, pod_id: str, run_id: str, authorization: str | None) -> dict:
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows = await postgrest_get(
        TABLE_RUNS,
        f"select=*&id=eq.{quote(run_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Run not found")
    run = rows[0]

    if str(run.get("pod_id")) != str(pod_id):
        # Avoid leaking existence across pods.
        raise HTTPException(status_code=404, detail="Run not found")

    if run.get("created_by") != user_id:
        roles = await postgrest_get("user_roles", f"select=role&user_id=eq.{quote(user_id, safe='')}&limit=1")
        role = roles[0].get("role") if roles else None
        if role not in {"admin", "global_admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
    return run


async def _queue_or_restart_training_job(
    *,
    pod_id: str,
    run_id: str,
    admin_id: Optional[str],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Ensure a training job is queued for a run.

    Behavior:
    - If no job exists: create + spawn.
    - If a job is queued/running: keep as-is (avoid duplicate workers).
    - If latest job is completed/failed: create a NEW job row and spawn.
    """
    existing_jobs = await postgrest_get(
        TABLE_JOBS,
        f"select=id,status&pod_id=eq.{quote(pod_id, safe='')}&run_id=eq.{quote(run_id, safe='')}"
        f"&order=created_at.desc&limit=1",
    )

    if not existing_jobs:
        job = await create_job_row(pod_id=pod_id, run_id=run_id, created_by=admin_id)
        background_tasks.add_task(spawn_job_runner, pod_id=pod_id, job_id=str(job["id"]), run_id=run_id)
        return

    existing = existing_jobs[0]
    job_id = str(existing.get("id"))
    status = str(existing.get("status") or "queued").lower()

    if status in {"queued", "running"}:
        logger.info(
            "Pods[approve] training job already %s for pod_id=%s run_id=%s (id=%s) — skipping respawn.",
            status,
            pod_id,
            run_id,
            job_id,
        )
        return

    job = await create_job_row(pod_id=pod_id, run_id=run_id, created_by=admin_id)
    new_job_id = str(job["id"])
    logger.info(
        "Pods[approve] creating new training job for pod_id=%s run_id=%s (new_id=%s, prev_id=%s, prev_status=%s).",
        pod_id,
        run_id,
        new_job_id,
        job_id,
        status,
    )
    background_tasks.add_task(spawn_job_runner, pod_id=pod_id, job_id=new_job_id, run_id=run_id)


@router.post("/{pod_id}/extract", response_model=PodExtractResponse)
async def extract_pod(
    pod_id: str,
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    extraction_hint: Optional[str] = Query(default=None, description="Optional pod-specific extraction hint"),
):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        result = await extract_and_prepare_pod_run(
            pod_id=pod_id,
            file=file,
            extraction_hint=extraction_hint,
            ingest_to_vectorstore=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extracted = result.extracted_json or {}
    overall_confidence = float(result.overall_confidence or 0.0)

    row = (await postgrest_insert(
        TABLE_RUNS,
        {
            "created_by": user_id,
            "pod_id": pod_id,
            "source_filename": file.filename,
            "source_mime": file.content_type,
            "raw_text": result.raw_text,
            "original_extracted_json": extracted,
            "extracted_json": extracted,
            "overall_confidence": overall_confidence,
            "status": "draft",
        },
    ))[0]

    return PodExtractResponse(
        run_id=str(row["id"]),
        status=row.get("status") or "draft",
        overall_confidence=overall_confidence,
        extracted=extracted,
    )


@router.get("/{pod_id}/runs/{run_id}")
async def get_pod_run(
    pod_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
):
    run = await _ensure_run_access(pod_id=pod_id, run_id=run_id, authorization=authorization)
    # Expose latest edited JSON (if any) while preserving immutable original extraction JSON.
    feedback_rows = await postgrest_get(
        TABLE_FEEDBACK,
        (
            "select=corrected_json,actor_role,created_at"
            f"&pod_id=eq.{quote(pod_id, safe='')}"
            f"&run_id=eq.{quote(run_id, safe='')}"
            "&order=created_at.desc&limit=20"
        ),
    )
    latest_corrected = None
    for fb in feedback_rows:
        if fb.get("corrected_json") is not None:
            latest_corrected = fb.get("corrected_json")
            break

    original_json = run.get("original_extracted_json")
    if original_json is None:
        original_json = run.get("extracted_json") or {}

    edited_json = latest_corrected if latest_corrected is not None else (run.get("extracted_json") or {})
    has_edits = latest_corrected is not None and latest_corrected != original_json

    run["original_extracted_json"] = original_json
    run["edited_extracted_json"] = edited_json
    run["has_edits"] = has_edits
    run["confidence_evaluation"] = _evaluate_confidence_and_feedback(
        base_confidence=float(run.get("overall_confidence") or 0.0),
        run_status=str(run.get("status") or ""),
        original_json=original_json if isinstance(original_json, dict) else {},
        edited_json=edited_json if isinstance(edited_json, dict) else {},
        feedback_rows=feedback_rows if isinstance(feedback_rows, list) else [],
    )
    return {"run": run}


@router.post("/{pod_id}/runs/{run_id}/re-extract", response_model=PodExtractResponse)
async def re_extract_run(
    pod_id: str,
    run_id: str,
    body: PodReExtractRequest,
    authorization: str | None = Header(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    run = await _ensure_run_access(pod_id=pod_id, run_id=run_id, authorization=authorization)
    extraction_hint = body.extraction_hint

    if file is not None:
        result = await extract_and_prepare_pod_run(
            pod_id=pod_id,
            file=file,
            extraction_hint=extraction_hint,
            ingest_to_vectorstore=True,
        )
        raw_text = result.raw_text
        extracted_json = result.extracted_json
        overall_confidence = float(result.overall_confidence or 0.0)
    else:
        raw_text = run.get("raw_text") or ""
        if not str(raw_text).strip():
            raise HTTPException(status_code=400, detail="No raw_text stored for this run.")
        extracted_json, overall_confidence = await extract_and_prepare_pod_reextract_from_raw_text(
            pod_id=pod_id,
            raw_text=str(raw_text),
            extraction_hint=extraction_hint,
        )

    await postgrest_patch(
        TABLE_RUNS,
        f"id=eq.{quote(run_id, safe='')}",
        {
            "status": "draft",
            "original_extracted_json": extracted_json,
            "extracted_json": extracted_json,
            "overall_confidence": overall_confidence,
            **({"raw_text": raw_text} if file is not None else {}),
        },
    )

    return PodExtractResponse(
        run_id=run_id,
        status="draft",
        overall_confidence=overall_confidence,
        extracted=extracted_json,
    )


@router.post("/{pod_id}/runs/{run_id}/submit")
async def submit_pod_run(
    pod_id: str,
    run_id: str,
    body: PodSubmitRequest,
    authorization: str | None = Header(default=None),
):
    run = await _ensure_run_access(pod_id=pod_id, run_id=run_id, authorization=authorization)
    user = await verify_user(authorization)
    user_id = user.get("id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    corrected = body.corrected_json if body.corrected_json is not None else None
    extracted = run.get("extracted_json") or {}
    if corrected is not None:
        extracted = corrected

    # Persist user feedback
    await postgrest_insert(
        TABLE_FEEDBACK,
        {
            "run_id": run_id,
            "pod_id": pod_id,
            "created_by": user_id,
            "actor_role": "user",
            "thumbs_up": body.thumbs_up,
            "notes": body.notes,
            "corrected_json": corrected,
        },
    )

    overall_confidence = float(run.get("overall_confidence") or 0.0)
    next_status = "needs_admin_review"
    queue_reason = "low_confidence_or_user_disagreed"
    if body.thumbs_up and overall_confidence >= _confidence_threshold() and not body.require_admin_approval_for_training:
        next_status = "approved"
        queue_reason = None

    # Update run status + extracted fields
    await postgrest_patch(
        TABLE_RUNS,
        f"id=eq.{quote(run_id, safe='')}",
        {"status": "submitted" if next_status != "approved" else "approved", "extracted_json": extracted},
    )

    if next_status == "approved":
        # If a queue row exists, mark it approved.
        try:
            await postgrest_patch(
                TABLE_QUEUE,
                f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
                {"state": "approved"},
            )
        except Exception:
            pass
        return {"status": "approved"}

    # Upsert queue row (insert then patch)
    try:
        await postgrest_insert(
            TABLE_QUEUE,
            {
                "run_id": run_id,
                "pod_id": pod_id,
                "priority": 0,
                "reason": queue_reason,
                "state": "open",
            },
        )
    except Exception:
        await postgrest_patch(
            TABLE_QUEUE,
            f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
            {"reason": queue_reason, "state": "open"},
        )

    await postgrest_patch(
        TABLE_RUNS,
        f"id=eq.{quote(run_id, safe='')}",
        {"status": "needs_admin_review"},
    )
    return {"status": "needs_admin_review"}


@router.get("/{pod_id}/runs")
async def list_user_runs(
    pod_id: str,
    authorization: str | None = Header(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    offset = (page - 1) * limit
    qs = (
        f"select=id,created_at,updated_at,source_filename,status,overall_confidence "
        f"&created_by=eq.{quote(user_id, safe='')}"
        f"&pod_id=eq.{quote(pod_id, safe='')}"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )
    if status:
        qs += f"&status=eq.{quote(status, safe='')}"

    rows = await postgrest_get(TABLE_RUNS, qs)
    return {"runs": rows, "page": page, "limit": limit}


@router.get("/{pod_id}/admin/queue/stats")
async def admin_queue_stats(pod_id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)
    all_rows = await postgrest_get(TABLE_QUEUE, f"select=state&pod_id=eq.{quote(pod_id, safe='')}")
    counts: dict[str, int] = {}
    for r in all_rows:
        s = r.get("state") or "unknown"
        counts[s] = counts.get(s, 0) + 1
    return {
        "open": counts.get("open", 0),
        "in_progress": counts.get("in_progress", 0),
        "rework": counts.get("rework", 0),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "total": len(all_rows),
    }


@router.get("/{pod_id}/admin/queue")
async def list_admin_queue(
    pod_id: str,
    authorization: str | None = Header(default=None),
    states: Optional[str] = Query(default="open,in_progress", description="Comma-separated queue states"),
    conf_min: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum confidence (0-1)"),
    conf_max: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Maximum confidence (0-1)"),
    order_by: str = Query(default="priority", description="priority|created_at|updated_at"),
    order_dir: str = Query(default="desc", description="asc|desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
):
    await _require_admin(authorization)

    valid_order = {"priority", "created_at", "updated_at"}
    valid_dir = {"asc", "desc"}
    ob = order_by if order_by in valid_order else "priority"
    od = order_dir if order_dir in valid_dir else "desc"

    offset = (page - 1) * limit
    state_list = [s.strip() for s in (states or "open,in_progress").split(",") if s.strip()]
    state_fragment = f"&state=in.({','.join(quote(s, safe='') for s in state_list)})"

    # Join run so we can confidence-filter in Python.
    qs = (
        f"select=*,{TABLE_RUNS}(*)&pod_id=eq.{quote(pod_id, safe='')}"
        f"{state_fragment}"
        f"&order={ob}.{od},created_at.asc"
        f"&limit={limit}&offset={offset}"
    )
    rows = await postgrest_get(TABLE_QUEUE, qs)

    if conf_min is not None or conf_max is not None:
        def _conf_ok(row: dict) -> bool:
            run = row.get(TABLE_RUNS) or {}
            conf = float(run.get("overall_confidence") or 0)
            if conf_min is not None and conf < conf_min:
                return False
            if conf_max is not None and conf > conf_max:
                return False
            return True

        rows = [r for r in rows if _conf_ok(r)]

    return {"queue": rows, "page": page, "limit": limit}


@router.post("/{pod_id}/admin/{run_id}/review")
async def admin_review_run(
    pod_id: str,
    run_id: str,
    body: PodAdminReviewRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    admin_id = (await verify_user(authorization)).get("id")

    decision = (body.decision or "").strip().lower()
    if decision not in {"approve", "rework", "reject"}:
        raise HTTPException(status_code=400, detail="Invalid decision")

    rows = await postgrest_get(TABLE_RUNS, f"select=*&id=eq.{quote(run_id, safe='')}&limit=1")
    if not rows:
        raise HTTPException(status_code=404, detail="Run not found")
    run = rows[0]

    extracted = run.get("extracted_json") or {}
    if body.corrected_json is not None:
        extracted = body.corrected_json
    else:
        latest_corrected = await _latest_corrected_json_for_run(pod_id=pod_id, run_id=run_id)
        if latest_corrected is not None:
            extracted = latest_corrected

    await postgrest_insert(
        TABLE_FEEDBACK,
        {
            "run_id": run_id,
            "pod_id": pod_id,
            "created_by": admin_id,
            "actor_role": "admin",
            "thumbs_up": decision == "approve",
            "notes": body.notes,
            "corrected_json": body.corrected_json,
        },
    )

    if decision == "approve":
        await postgrest_patch(TABLE_RUNS, f"id=eq.{quote(run_id, safe='')}", {"status": "approved", "extracted_json": extracted})
        await postgrest_patch(
            TABLE_QUEUE,
            f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
            {"state": "approved", "assigned_to": body.assigned_to},
        )
        await _queue_or_restart_training_job(
            pod_id=pod_id,
            run_id=run_id,
            admin_id=admin_id,
            background_tasks=background_tasks,
        )
        return {"status": "approved"}

    if decision == "reject":
        await postgrest_patch(TABLE_RUNS, f"id=eq.{quote(run_id, safe='')}", {"status": "rejected", "extracted_json": extracted})
        await postgrest_patch(
            TABLE_QUEUE,
            f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
            {"state": "rejected", "assigned_to": body.assigned_to},
        )
        return {"status": "rejected"}

    # rework
    await postgrest_patch(
        TABLE_RUNS,
        f"id=eq.{quote(run_id, safe='')}",
        {"status": "needs_admin_review", "extracted_json": extracted},
    )
    await postgrest_patch(
        TABLE_QUEUE,
        f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
        {"state": "rework", "assigned_to": body.assigned_to},
    )
    return {"status": "needs_admin_review"}


@router.post("/{pod_id}/admin/batch-review")
async def batch_review_runs(
    pod_id: str,
    body: PodBatchReviewRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    admin_id = (await verify_user(authorization)).get("id")

    decision = (body.decision or "").strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Batch decision must be approve or reject")

    run_status = "approved" if decision == "approve" else "rejected"
    queue_state = run_status

    results: list[dict] = []
    for run_id in body.run_ids:
        try:
            await postgrest_insert(
                TABLE_FEEDBACK,
                {
                    "run_id": run_id,
                    "pod_id": pod_id,
                    "created_by": admin_id,
                    "actor_role": "admin",
                    "thumbs_up": decision == "approve",
                    "notes": body.notes,
                },
            )
            await postgrest_patch(TABLE_RUNS, f"id=eq.{quote(run_id, safe='')}", {"status": run_status})
            await postgrest_patch(
                TABLE_QUEUE,
                f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}",
                {"state": queue_state, "assigned_to": None},
            )
            if decision == "approve":
                await _queue_or_restart_training_job(
                    pod_id=pod_id,
                    run_id=run_id,
                    admin_id=admin_id,
                    background_tasks=background_tasks,
                )
            results.append({"run_id": run_id, "ok": True})
        except Exception as exc:
            logger.warning("Pods[batch] review failed pod_id=%s run_id=%s: %s", pod_id, run_id, exc)
            results.append({"run_id": run_id, "ok": False, "error": str(exc)})

    return {
        "decision": decision,
        "succeeded": sum(1 for r in results if r.get("ok")),
        "total": len(results),
        "results": results,
    }


@router.get("/{pod_id}/admin/queue/{run_id}/detail")
async def get_admin_queue_item(
    pod_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    rows = await postgrest_get(
        TABLE_QUEUE,
        f"select=*,{TABLE_RUNS}(*)&run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return {"item": rows[0]}


@router.patch("/{pod_id}/admin/queue/{run_id}/detail")
async def patch_admin_queue_item(
    pod_id: str,
    run_id: str,
    body: dict,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    allowed = {"priority", "assigned_to", "state"}
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(status_code=400, detail=f"No valid fields to patch. Allowed: {sorted(allowed)}")
    await postgrest_patch(TABLE_QUEUE, f"run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}", patch)
    return {"updated": patch}


# -------------------------------
# Training job endpoints
# -------------------------------


@router.get("/{pod_id}/admin/jobs")
async def list_training_jobs(
    pod_id: str,
    authorization: str | None = Header(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    await _require_admin(authorization)
    offset = (page - 1) * limit
    qs = f"select=id,created_at,updated_at,run_id,status,started_at,finished_at,error,log_path&pod_id=eq.{quote(pod_id, safe='')}&order=created_at.desc&limit={limit}&offset={offset}"
    if status:
        qs += f"&status=eq.{quote(status, safe='')}"
    rows = await postgrest_get(TABLE_JOBS, qs)
    return {"jobs": rows, "page": page, "limit": limit}


@router.get("/{pod_id}/admin/jobs/by-run/{run_id}")
async def get_job_by_run_id(
    pod_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    rows = await postgrest_get(
        TABLE_JOBS,
        f"select=*&run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&order=created_at.desc&limit=1",
    )
    if not rows:
        return {"job": None}
    return {"job": rows[0]}


@router.get("/{pod_id}/admin/jobs/by-run/{run_id}/history")
async def get_job_history_by_run_id(
    pod_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=25, ge=1, le=200),
):
    await _require_admin(authorization)
    rows = await postgrest_get(
        TABLE_JOBS,
        f"select=id,created_at,updated_at,run_id,status,started_at,finished_at,error,log_path,dataset_path,output_dir&run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&order=created_at.desc&limit={limit}",
    )
    return {"jobs": rows}


@router.get("/{pod_id}/admin/jobs/{job_id}")
async def get_training_job(
    pod_id: str,
    job_id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    rows = await postgrest_get(
        TABLE_JOBS,
        f"select=*&id=eq.{quote(job_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": rows[0]}


@router.get("/{pod_id}/admin/jobs/{job_id}/eval")
async def get_job_eval_results(
    pod_id: str,
    job_id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    rows = await postgrest_get(
        TABLE_EVAL_RESULTS,
        f"select=*&job_id=eq.{quote(job_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&order=eval_set.asc",
    )
    return {"eval_results": rows}


@router.get("/{pod_id}/admin/runs/{run_id}/health-card")
async def get_run_health_card(
    pod_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)
    run_rows = await postgrest_get(
        TABLE_RUNS,
        f"select=id,created_at,updated_at,status,overall_confidence,extracted_json,original_extracted_json,pod_id"
        f"&id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&limit=1",
    )
    if not run_rows:
        raise HTTPException(status_code=404, detail="Run not found")
    run = run_rows[0]

    feedback_rows = await postgrest_get(
        TABLE_FEEDBACK,
        (
            "select=corrected_json,thumbs_up,actor_role,created_at"
            f"&pod_id=eq.{quote(pod_id, safe='')}"
            f"&run_id=eq.{quote(run_id, safe='')}"
            "&order=created_at.desc&limit=50"
        ),
    )
    original_json = run.get("original_extracted_json")
    if original_json is None:
        original_json = run.get("extracted_json") or {}
    edited_json = run.get("extracted_json") or {}
    confidence_eval = _evaluate_confidence_and_feedback(
        base_confidence=float(run.get("overall_confidence") or 0.0),
        run_status=str(run.get("status") or ""),
        original_json=original_json if isinstance(original_json, dict) else {},
        edited_json=edited_json if isinstance(edited_json, dict) else {},
        feedback_rows=feedback_rows if isinstance(feedback_rows, list) else [],
    )

    job_rows = await postgrest_get(
        TABLE_JOBS,
        f"select=*&run_id=eq.{quote(run_id, safe='')}&pod_id=eq.{quote(pod_id, safe='')}&order=created_at.desc&limit=1",
    )
    latest_job = job_rows[0] if job_rows else None
    eval_rows: list[dict] = []
    gate_snapshot: Optional[dict] = None
    if latest_job:
        eval_rows = await postgrest_get(
            TABLE_EVAL_RESULTS,
            f"select=*&job_id=eq.{quote(str(latest_job.get('id')), safe='')}&pod_id=eq.{quote(pod_id, safe='')}&order=eval_set.asc",
        )
        gate_snapshot = _quality_gate_snapshot_from_eval_rows(eval_rows)

    return {
        "run": run,
        "confidence_evaluation": confidence_eval,
        "latest_training_job": latest_job,
        "latest_eval_results": eval_rows,
        "quality_gate_snapshot": gate_snapshot,
    }


def _read_tail_text(path: Path, max_lines: int) -> str:
    """
    Read last N lines without loading the entire file.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def _progress_from_log_tail(log_text: str, status: str) -> Optional[int]:
    if not log_text:
        return None
    if status in {"completed", "failed"}:
        return 100
    percent_matches = re.findall(r"(\d{1,3})%\s*\|", log_text) or re.findall(r"(\d{1,3})%", log_text)
    if percent_matches:
        try:
            return max(0, min(100, int(percent_matches[-1])))
        except Exception:
            return None
    if "Running evaluation" in log_text:
        return 85
    return None


@router.get("/{pod_id}/admin/jobs/{job_id}/log")
async def get_job_log_tail(
    pod_id: str,
    job_id: str,
    authorization: str | None = Header(default=None),
    tail: int = Query(default=200, ge=1, le=2000),
):
    await _require_admin(authorization)

    rows = await postgrest_get(
        TABLE_JOBS,
        f"select=id,created_at,updated_at,status,log_path,error&pod_id=eq.{quote(pod_id, safe='')}&id=eq.{quote(job_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    job = rows[0]
    status = job.get("status") or "queued"
    log_path = job.get("log_path")

    tail_text = ""
    progress_percent: Optional[int] = None

    if log_path:
        try:
            resolved = Path(str(log_path)).resolve()
            backend_dir = Path(__file__).resolve().parents[2]
            allowed_base = (backend_dir / "fine_tuning" / "runs").resolve()
            if not any(p == allowed_base for p in resolved.parents) and resolved != allowed_base:
                raise HTTPException(status_code=403, detail="Log path is not allowed.")
            if resolved.exists():
                tail_text = _read_tail_text(resolved, max_lines=tail)
                progress_percent = _progress_from_log_tail(tail_text, status=str(status))
            else:
                tail_text = f"[log missing] file not found at: {resolved}"
        except HTTPException:
            raise
        except Exception as exc:
            tail_text = f"[log tail unavailable] {exc}"
            progress_percent = _progress_from_log_tail(tail_text, status=str(status))
    else:
        tail_text = "[log missing] log_path is not set for this job row."

    if not tail_text.strip():
        err = str(job.get("error") or "").strip()
        if err:
            tail_text = f"[no log tail] Using stored job error:\n{err}"
        else:
            tail_text = "[no log tail] Job log is empty or inaccessible."

    return {
        "job_id": job_id,
        "status": status,
        "updated_at": job.get("updated_at"),
        "progress_percent": progress_percent,
        "tail_text": tail_text,
        "error": job.get("error"),
    }

