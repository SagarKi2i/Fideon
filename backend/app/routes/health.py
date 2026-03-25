import json
from typing import Any

import httpx
from fastapi import APIRouter

from app.core.config import (
    ANTHROPIC_API_KEY,
    FIDEON_SECRET_KEY,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    GROQ_OPENAI_COMPAT_URL,
    GROQ_MODEL_HELP,
    OFFLINE_LLM_FALLBACK_ENABLED,
    OPENAI_API_KEY,
    RUNPOD_API_KEY,
    RUNPOD_GENERATE_URL,
    RUNPOD_MODEL_LLAMA,
    RUNPOD_OPENAI_COMPAT_URL,
)
from app.services.llm import llm_stream

router = APIRouter()
CONTENT_TYPE_JSON = "application/json"


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/healthy")
async def healthy_alias():
    """Same as /health — common typo for probes and bookmarks."""
    return {"ok": True}


def _is_enabled(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _extract_first_sse_chunk(raw_chunk: bytes) -> dict[str, Any] | None:
    text = raw_chunk.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


async def _provider_probe(
    client: httpx.AsyncClient,
    *,
    configured: bool,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    ok_on_2xx_only: bool,
) -> dict[str, Any]:
    if not configured:
        return {"configured": False, "ok": False, "error": "not_configured"}
    result: dict[str, Any] = {"configured": True, "ok": False}
    try:
        resp = await client.post(url, headers=headers, json=payload)
        result["status_code"] = resp.status_code
        result["ok"] = resp.status_code == 200 if ok_on_2xx_only else resp.status_code < 400
        if not result["ok"]:
            result["error"] = resp.text[:200]
    except Exception as exc:
        result["error"] = str(exc)
    return result


@router.get("/api/llm-health")
async def llm_health():
    providers = {
        "groq": bool(GROQ_API_KEY),
        "runpod_generate": bool((FIDEON_SECRET_KEY or RUNPOD_API_KEY) and RUNPOD_GENERATE_URL),
        "runpod_openai_compat": bool((FIDEON_SECRET_KEY or RUNPOD_API_KEY) and RUNPOD_OPENAI_COMPAT_URL),
        "gemini": bool(GEMINI_API_KEY),
        "openai": bool(OPENAI_API_KEY),
        "claude": bool(ANTHROPIC_API_KEY),
        "offline_fallback_enabled": _is_enabled(OFFLINE_LLM_FALLBACK_ENABLED),
    }
    try:
        status, _, stream = await llm_stream(
            {
                "model": GROQ_MODEL_HELP,
                "messages": [
                    {"role": "system", "content": "Health check probe."},
                    {"role": "user", "content": "Reply with: OK"},
                ],
                "stream": True,
            }
        )
        first_chunk = await stream.__anext__()
        parsed = _extract_first_sse_chunk(first_chunk)
        try:
            await stream.aclose()
        except Exception:
            pass

        model = (parsed or {}).get("model", "")
        probe_provider = "unknown"
        if isinstance(model, str):
            lowered = model.lower()
            if "llama" in lowered or "mixtral" in lowered or "qwen" in lowered:
                # Could be Groq or RunPod. Keep this generic and expose model string.
                probe_provider = "groq_or_runpod"
            elif lowered == "offline-llm":
                probe_provider = "offline-llm"
            elif "gemini" in lowered:
                probe_provider = "gemini"
            elif "gpt" in lowered:
                probe_provider = "openai"
            elif "claude" in lowered:
                probe_provider = "claude"

        return {
            "ok": status == 200,
            "probe_status": status,
            "probe_provider": probe_provider,
            "probe_model": model,
            "providers_configured": providers,
        }
    except Exception as exc:
        return {
            "ok": False,
            "probe_error": str(exc),
            "providers_configured": providers,
        }


def _clean_token(raw_token: str) -> str:
    token = (raw_token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


@router.get("/api/llm-health/providers")
async def llm_health_providers():
    """
    Provider-level diagnostics with explicit checks for Groq and RunPod.
    This helps verify fallback readiness without leaking any secrets.
    """
    runpod_token = _clean_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)
    checks: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=15) as client:
        checks["groq"] = await _provider_probe(
            client,
            configured=bool(GROQ_API_KEY),
            url=GROQ_OPENAI_COMPAT_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": CONTENT_TYPE_JSON,
            },
            payload={
                "model": GROQ_MODEL_HELP,
                "messages": [{"role": "user", "content": "Reply with OK"}],
                "stream": False,
                "temperature": 0,
            },
            ok_on_2xx_only=True,
        )
        checks["runpod_generate"] = await _provider_probe(
            client,
            configured=bool(runpod_token and RUNPOD_GENERATE_URL),
            url=RUNPOD_GENERATE_URL,
            headers={
                "Authorization": f"Bearer {runpod_token}",
                "x-api-key": runpod_token,
                "Content-Type": CONTENT_TYPE_JSON,
            },
            payload={"prompt": "health check", "model": RUNPOD_MODEL_LLAMA},
            ok_on_2xx_only=False,
        )
        checks["runpod_openai_compat"] = await _provider_probe(
            client,
            configured=bool(runpod_token and RUNPOD_OPENAI_COMPAT_URL),
            url=RUNPOD_OPENAI_COMPAT_URL,
            headers={
                "Authorization": f"Bearer {runpod_token}",
                "x-api-key": runpod_token,
                "Content-Type": CONTENT_TYPE_JSON,
            },
            payload={
                "model": RUNPOD_MODEL_LLAMA,
                "messages": [{"role": "user", "content": "Reply with OK"}],
                "stream": False,
                "temperature": 0,
            },
            ok_on_2xx_only=False,
        )

    overall_ok = all(
        item.get("ok")
        for item in checks.values()
        if item.get("configured")
    )
    return {
        "ok": overall_ok,
        "checks": checks,
    }
