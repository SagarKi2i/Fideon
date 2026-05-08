"""BFF: orchestrate RunPod (GraphQL RUNNING + optional SSH + wait ML HTTP) then proxy ACORD extract."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.core.config import RUNPOD_ML_ACORD_EXTRACT_PATH, runpod_proxy_base_url
from app.core.supabase import verify_user
from app.services.runpod_orchestrator import ensure_runpod_ml_ready

router = APIRouter(tags=["ml-acord"])


@router.post("/api/v1/ml/acord/extract")
async def proxy_acord_extract(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    form_type_hint: Optional[str] = Query(
        default=None,
        description="e.g. '25', '125' — forwarded to ML server as query param",
    ),
):
    """
    Authenticated users: ensure RunPod ML stack is up, then POST multipart to Akshay
    `POST /api/acord/extract` with the same Supabase JWT (same project as main app).
    """
    await verify_user(authorization)
    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="Authorization header required")

    await ensure_runpod_ml_ready()

    base = runpod_proxy_base_url().strip().rstrip("/")
    path = RUNPOD_ML_ACORD_EXTRACT_PATH if RUNPOD_ML_ACORD_EXTRACT_PATH.startswith("/") else f"/{RUNPOD_ML_ACORD_EXTRACT_PATH}"
    q = urlencode({"form_type_hint": form_type_hint}) if form_type_hint else ""
    url = f"{base}{path}" + (f"?{q}" if q else "")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "upload.bin"
    mime = file.content_type or "application/octet-stream"

    headers = {"Authorization": authorization.strip()}

    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=60.0)) as client:
        try:
            r = await client.post(
                url,
                headers=headers,
                files={"file": (filename, content, mime)},
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"ML server unreachable: {e}") from e

    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type") or "application/json",
    )
