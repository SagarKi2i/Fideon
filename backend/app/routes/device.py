from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import get_device_by_token, postgrest_get, postgrest_patch

router = APIRouter()


@router.get("/api/device-models")
async def device_models(x_device_token: Optional[str] = Header(default=None)):
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
    device = await get_device_by_token(x_device_token)
    models = await postgrest_get(
        "device_models",
        f"select=*&device_id=eq.{quote(device['id'], safe='')}&order=allocated_at.desc",
    )
    mapped = [
        {
            "model_id": m.get("model_id"),
            "model_name": m.get("model_name"),
            "domain": m.get("domain"),
            "ollama_model_name": m.get("ollama_model_name") or "llama3.2:latest",
            "is_downloaded": m.get("is_downloaded"),
            "allocated_at": m.get("allocated_at"),
        }
        for m in models
    ]
    return {"success": True, "device_id": device["id"], "models": mapped, "total_models": len(mapped)}


@router.post("/api/device-checkin")
async def device_checkin(request: Request, x_device_token: Optional[str] = Header(default=None)):
    if not x_device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
    device = await get_device_by_token(x_device_token)
    body = await request.json()
    os_type = body.get("os_type")
    app_version = body.get("app_version")
    local_models = body.get("local_models", [])

    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device['id'], safe='')}",
        {
            "status": "online",
            "last_seen_at": datetime.utcnow().isoformat(),
            "os_type": os_type or device.get("os_type"),
            "app_version": app_version or device.get("app_version"),
        },
    )

    if isinstance(local_models, list):
        for local_model in local_models:
            model_id = local_model.get("model_id") if isinstance(local_model, dict) else local_model
            if model_id:
                await postgrest_patch(
                    "device_models",
                    f"device_id=eq.{quote(device['id'], safe='')}&model_id=eq.{quote(str(model_id), safe='')}",
                    {"is_downloaded": True, "last_synced_at": datetime.utcnow().isoformat()},
                )

    return {"success": True, "device_id": device["id"], "status": "online", "message": "Check-in successful"}


@router.post("/api/device-register")
async def device_register(request: Request):
    body = await request.json()
    device_token = body.get("device_token")
    if not device_token:
        raise HTTPException(status_code=400, detail="Device token is required")
    device = await get_device_by_token(device_token)
    await postgrest_patch(
        "devices",
        f"id=eq.{quote(device['id'], safe='')}",
        {
            "device_name": body.get("device_name") or device.get("device_name"),
            "os_type": body.get("os_type") or device.get("os_type"),
            "app_version": body.get("app_version") or device.get("app_version"),
            "status": "online",
            "last_seen_at": datetime.utcnow().isoformat(),
        },
    )
    return {
        "success": True,
        "device_id": device["id"],
        "device_name": device.get("device_name"),
        "message": "Device registered successfully",
    }
