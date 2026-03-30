"""RunPod pod control + proxy query (ported from llm-gateway control_server.py).

Requires admin or global_admin. Configure RUNPOD_POD_ID and RUNPOD_API_KEY; optional RUNPOD_PROXY_BASE_URL.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import (
    FIDEON_SECRET_KEY,
    RUNPOD_API_KEY,
    RUNPOD_GENERATE_URL,
    RUNPOD_POD_ID,
    runpod_proxy_base_url,
)
from app.core.supabase import postgrest_get, verify_user
from app.services.runpod_orchestrator import ensure_runpod_ml_ready

router = APIRouter()

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"


def _graphql_headers() -> dict[str, str]:
    if not RUNPOD_API_KEY:
        raise HTTPException(status_code=503, detail="RUNPOD_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


def _generate_auth_headers() -> dict[str, str]:
    token = (FIDEON_SECRET_KEY or RUNPOD_API_KEY or "").strip()
    h: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _require_admin(authorization: Optional[str]) -> None:
    user = await verify_user(authorization)
    uid = user.get("id")
    if not uid:
        raise HTTPException(status_code=403, detail="Invalid user")
    rows = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(str(uid), safe='')}&limit=1"
    )
    role = rows[0].get("role") if rows else None
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_pod_id() -> None:
    if not RUNPOD_POD_ID:
        raise HTTPException(status_code=503, detail="RUNPOD_POD_ID is not configured")


class QueryRequest(BaseModel):
    prompt: str
    max_tokens: int = 200
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


async def _graphql(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(RUNPOD_GRAPHQL, json=body, headers=_graphql_headers())
        r.raise_for_status()
        data = r.json()
    if data.get("errors"):
        raise HTTPException(status_code=502, detail=str(data["errors"]))
    return data


@router.get("/api/v1/runpod/pod-health")
async def pod_health(authorization: Optional[str] = Header(default=None)):
    """GET RunPod proxy root (or /health) — same idea as llm-gateway GET /pod/health."""
    await _require_admin(authorization)
    base = runpod_proxy_base_url().strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Configure RUNPOD_PROXY_BASE_URL or RUNPOD_GENERATE_URL")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base}/")
            if r.status_code == 200:
                try:
                    details: Any = r.json()
                except Exception:
                    details = {"raw": r.text[:500]}
                return {"status": "healthy", "details": details}
            return {"status": "unhealthy", "status_code": r.status_code}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/api/v1/runpod/pod-status")
async def pod_status(authorization: Optional[str] = Header(default=None)):
    """GraphQL pod status — same idea as llm-gateway GET /pod/status."""
    await _require_admin(authorization)
    _require_pod_id()
    try:
        data = await _graphql(
            {
                "query": f"""
                query {{
                    pod(input: {{ podId: "{RUNPOD_POD_ID}" }}) {{
                        id
                        name
                        desiredStatus
                        runtime {{
                            uptimeInSeconds
                        }}
                    }}
                }}
                """
            }
        )
        pod_data = (data.get("data") or {}).get("pod")
        if pod_data is None:
            return {"error": "Pod not found", "full_response": data}
        runtime = pod_data.get("runtime") or {}
        return {
            "pod_id": pod_data.get("id"),
            "status": pod_data.get("desiredStatus"),
            "uptime": runtime.get("uptimeInSeconds"),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


async def _pod_resume_mutation() -> dict[str, Any]:
    data = await _graphql(
        {
            "query": f"""
            mutation {{
                podResume(input: {{ podId: "{RUNPOD_POD_ID}" }}) {{
                    id
                    desiredStatus
                }}
            }}
            """
        }
    )
    pod_data = (data.get("data") or {}).get("podResume")
    if pod_data is None:
        return {"error": "Failed to start pod", "full_response": data}
    return {
        "message": "Pod starting...",
        "pod_id": pod_data.get("id"),
        "status": pod_data.get("desiredStatus"),
    }


@router.post("/api/v1/runpod/pod-start")
async def start_pod(authorization: Optional[str] = Header(default=None)):
    await _require_admin(authorization)
    _require_pod_id()
    try:
        return await _pod_resume_mutation()
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/v1/runpod/pod-stop")
async def stop_pod(authorization: Optional[str] = Header(default=None)):
    await _require_admin(authorization)
    _require_pod_id()
    try:
        data = await _graphql(
            {
                "query": f"""
                mutation {{
                    podStop(input: {{ podId: "{RUNPOD_POD_ID}" }}) {{
                        id
                        desiredStatus
                    }}
                }}
                """
            }
        )
        pod_data = (data.get("data") or {}).get("podStop")
        if pod_data is None:
            return {"error": "Failed to stop pod", "full_response": data}
        return {
            "message": "Pod stopping...",
            "pod_id": pod_data.get("id"),
            "status": pod_data.get("desiredStatus"),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/v1/runpod/query")
async def query_llm(req: QueryRequest, authorization: Optional[str] = Header(default=None)):
    """Resume pod if needed, wait for proxy health, POST /generate on RunPod proxy."""
    await _require_admin(authorization)
    _require_pod_id()
    if not runpod_proxy_base_url():
        raise HTTPException(status_code=503, detail="RunPod proxy base URL is not configured")
    gen_url = (RUNPOD_GENERATE_URL or "").strip()
    if not gen_url:
        raise HTTPException(status_code=503, detail="RUNPOD_GENERATE_URL is not configured")

    try:
        await ensure_runpod_ml_ready()

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                gen_url,
                json={
                    "prompt": f"Answer clearly:\n{req.prompt}",
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                },
                headers=_generate_auth_headers(),
            )
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
            return {"raw": r.text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
