"""
User data API — replaces all direct frontend → Supabase PostgREST calls for
the following tables (owner-scoped, JWT authenticated):

  activated_models, chat_conversations, documents,
  workflows, workflow_runs,
  agent_schedules, agent_pipelines
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import (
    postgrest_delete,
    postgrest_get,
    postgrest_insert,
    postgrest_patch,
    verify_user,
)

router = APIRouter()


async def _uid(authorization: Optional[str]) -> str:
    user = await verify_user(authorization)
    uid = user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return uid


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVATED MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/activated-models")
async def list_activated_models(
    model_id: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """Return the calling user's activated models."""
    uid = await _uid(authorization)
    q = f"select=*&user_id=eq.{quote(uid, safe='')}&order=activated_at.desc"
    if model_id:
        q += f"&model_id=eq.{quote(model_id, safe='')}"
    rows = await postgrest_get("activated_models", q)
    return {"activated_models": rows}


@router.delete("/api/v1/activated-models/{record_id}")
async def delete_activated_model(
    record_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Deactivate a model (delete the row — user-owns-row check via filter)."""
    uid = await _uid(authorization)
    await postgrest_delete(
        "activated_models",
        f"id=eq.{quote(record_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/chat-conversations")
async def list_chat_conversations(
    model_ids: Optional[str] = None,   # comma-separated model IDs to filter
    authorization: Optional[str] = Header(default=None),
):
    """Return the calling user's chat conversations."""
    uid = await _uid(authorization)
    q = (
        "select=id,model_id,updated_at,title,chat_messages(id,created_at)"
        f"&user_id=eq.{quote(uid, safe='')}"
    )
    if model_ids:
        ids = ",".join(quote(m.strip(), safe="") for m in model_ids.split(",") if m.strip())
        if ids:
            q += f"&model_id=in.({ids})"
    rows = await postgrest_get("chat_conversations", q)
    return {"conversations": rows}


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/documents")
async def list_documents(
    authorization: Optional[str] = Header(default=None),
):
    """Return documents owned by the calling user (PDF / Word)."""
    uid = await _uid(authorization)
    rows = await postgrest_get(
        "documents",
        (
            f"select=id,filename,file_type&user_id=eq.{quote(uid, safe='')}"
            "&or=(file_type.eq.application/pdf,file_type.ilike.*word*)"
        ),
    )
    return {"documents": rows}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/workflows")
async def list_workflows(
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    rows = await postgrest_get(
        "workflows",
        f"select=*&user_id=eq.{quote(uid, safe='')}&order=created_at.desc",
    )
    return {"workflows": rows}


@router.post("/api/v1/workflows", status_code=201)
async def create_workflow(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    payload: Dict[str, Any] = {
        "user_id": uid,
        "title": str(body.get("title") or "").strip(),
        "description": str(body.get("description") or "").strip() or None,
        "sop_text": body.get("sop_text"),
        "category": body.get("category"),
        "parsed_steps": body.get("parsed_steps"),
    }
    if not payload["title"]:
        raise HTTPException(status_code=400, detail="title is required")
    rows = await postgrest_insert("workflows", payload)
    return {"workflow": rows[0] if rows else None}


@router.patch("/api/v1/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    allowed = {"title", "description", "sop_text", "category", "parsed_steps"}
    patch: Dict[str, Any] = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if "title" in patch and not str(patch["title"]).strip():
        raise HTTPException(status_code=400, detail="title cannot be empty")
    await postgrest_patch(
        "workflows",
        f"id=eq.{quote(workflow_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
        patch,
    )
    return {"success": True}


@router.delete("/api/v1/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    await postgrest_delete(
        "workflows",
        f"id=eq.{quote(workflow_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
    )
    return {"success": True}


@router.get("/api/v1/workflows/{workflow_id}/versions")
async def list_workflow_versions(
    workflow_id: str,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    # Verify ownership
    rows = await postgrest_get(
        "workflows",
        f"select=id&id=eq.{quote(workflow_id, safe='')}&user_id=eq.{quote(uid, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    versions = await postgrest_get(
        "workflow_versions",
        f"select=id,version_number,title,description,sop_text,category,parsed_steps,created_at"
        f"&workflow_id=eq.{quote(workflow_id, safe='')}"
        f"&order=version_number.desc&limit=10",
    )
    return {"versions": versions}


@router.post("/api/v1/workflows/{workflow_id}/restore/{version_number}")
async def restore_workflow_version(
    workflow_id: str,
    version_number: int,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    # Verify ownership
    wf_rows = await postgrest_get(
        "workflows",
        f"select=id&id=eq.{quote(workflow_id, safe='')}&user_id=eq.{quote(uid, safe='')}&limit=1",
    )
    if not wf_rows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Fetch the requested version
    ver_rows = await postgrest_get(
        "workflow_versions",
        f"select=title,description,sop_text,category,parsed_steps"
        f"&workflow_id=eq.{quote(workflow_id, safe='')}"
        f"&version_number=eq.{version_number}&limit=1",
    )
    if not ver_rows:
        raise HTTPException(status_code=404, detail="Version not found")
    ver = ver_rows[0]
    # Patch the workflow (the DB trigger will snapshot current state first)
    await postgrest_patch(
        "workflows",
        f"id=eq.{quote(workflow_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
        {
            "title": ver["title"],
            "description": ver.get("description"),
            "sop_text": ver["sop_text"],
            "category": ver.get("category"),
            "parsed_steps": ver.get("parsed_steps", []),
        },
    )
    return {"success": True, "restored_to_version": version_number}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW RUNS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/workflow-runs")
async def list_workflow_runs(
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    rows = await postgrest_get(
        "workflow_runs",
        (
            f"select=id,status,started_at,completed_at"
            f"&user_id=eq.{quote(uid, safe='')}"
            f"&order=started_at.desc&limit={min(limit, 500)}"
        ),
    )
    return {"workflow_runs": rows}


@router.post("/api/v1/workflow-runs", status_code=201)
async def create_workflow_run(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    payload: Dict[str, Any] = {
        "workflow_id": body.get("workflow_id"),
        "user_id": uid,
        "status": body.get("status", "running"),
        "current_step": body.get("current_step", 0),
        "step_results": body.get("step_results"),
    }
    if not payload["workflow_id"]:
        raise HTTPException(status_code=400, detail="workflow_id is required")

    from app.core.supabase import postgrest_insert as _insert
    # Use prefer: return=representation
    from app.core.supabase import service_headers
    import httpx
    from app.core.config import SUPABASE_URL
    headers = service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/workflow_runs",
            headers=headers,
            content=json.dumps(payload),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=500, detail=resp.text)
    rows = resp.json()
    return {"workflow_run": rows[0] if isinstance(rows, list) and rows else rows}


@router.patch("/api/v1/workflow-runs/{run_id}")
async def update_workflow_run(
    run_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    allowed = {"current_step", "step_results", "status", "completed_at"}
    patch: Dict[str, Any] = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await postgrest_patch(
        "workflow_runs",
        f"id=eq.{quote(run_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
        patch,
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/agent-schedules")
async def list_agent_schedules(authorization: Optional[str] = Header(default=None)):
    uid = await _uid(authorization)
    rows = await postgrest_get(
        "agent_schedules",
        f"select=*&user_id=eq.{quote(uid, safe='')}&order=created_at.desc",
    )
    return {"agent_schedules": rows}


@router.post("/api/v1/agent-schedules", status_code=201)
async def create_agent_schedule(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    payload: Dict[str, Any] = {
        "user_id": uid,
        "model_id": body.get("model_id"),
        "model_name": body.get("model_name"),
        "schedule_type": body.get("schedule_type"),
        "cron_expression": body.get("cron_expression"),
        "scheduled_at": body.get("scheduled_at"),
        "prompt": body.get("prompt"),
        "next_run_at": body.get("next_run_at"),
    }
    rows = await postgrest_insert("agent_schedules", payload)
    return {"agent_schedule": rows[0] if rows else None}


@router.patch("/api/v1/agent-schedules/{schedule_id}")
async def update_agent_schedule(
    schedule_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    allowed = {"model_id", "model_name", "schedule_type", "cron_expression", "scheduled_at", "prompt", "next_run_at", "is_active"}
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await postgrest_patch(
        "agent_schedules",
        f"id=eq.{quote(schedule_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
        patch,
    )
    return {"success": True}


@router.delete("/api/v1/agent-schedules/{schedule_id}")
async def delete_agent_schedule(
    schedule_id: str,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    await postgrest_delete(
        "agent_schedules",
        f"id=eq.{quote(schedule_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT PIPELINES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/agent-pipelines")
async def list_agent_pipelines(authorization: Optional[str] = Header(default=None)):
    uid = await _uid(authorization)
    rows = await postgrest_get(
        "agent_pipelines",
        f"select=*&user_id=eq.{quote(uid, safe='')}&order=created_at.desc",
    )
    return {"agent_pipelines": rows}


@router.post("/api/v1/agent-pipelines", status_code=201)
async def create_agent_pipeline(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    payload: Dict[str, Any] = {
        "user_id": uid,
        "name": str(body.get("name") or "").strip(),
        "description": body.get("description"),
        "steps": body.get("steps"),
        "schedule_config": body.get("schedule_config"),
    }
    if not payload["name"]:
        raise HTTPException(status_code=400, detail="name is required")
    rows = await postgrest_insert("agent_pipelines", payload)
    return {"agent_pipeline": rows[0] if rows else None}


@router.patch("/api/v1/agent-pipelines/{pipeline_id}")
async def update_agent_pipeline(
    pipeline_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    body = await request.json()
    allowed = {"name", "description", "steps", "schedule_config", "is_active"}
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await postgrest_patch(
        "agent_pipelines",
        f"id=eq.{quote(pipeline_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
        patch,
    )
    return {"success": True}


@router.delete("/api/v1/agent-pipelines/{pipeline_id}")
async def delete_agent_pipeline(
    pipeline_id: str,
    authorization: Optional[str] = Header(default=None),
):
    uid = await _uid(authorization)
    await postgrest_delete(
        "agent_pipelines",
        f"id=eq.{quote(pipeline_id, safe='')}&user_id=eq.{quote(uid, safe='')}",
    )
    return {"success": True}
