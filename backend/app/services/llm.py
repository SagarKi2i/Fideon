import json
import logging
from typing import Any, AsyncGenerator

import httpx
from fastapi import HTTPException

from app.core.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MESSAGES_URL,
    CLAUDE_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_OPENAI_COMPAT_URL,
    OPENAI_API_KEY,
    OPENAI_CHAT_COMPLETIONS_URL,
    OPENAI_MODEL,
    FIDEON_SECRET_KEY,
    RUNPOD_API_KEY,
    RUNPOD_GENERATE_URL,
    RUNPOD_MODEL_LLAMA,
    RUNPOD_MODEL_MISTRAL,
    RUNPOD_OPENAI_COMPAT_URL,
    OFFLINE_LLM_FALLBACK_ENABLED,
    LLM_CACHE_BACKEND,
    LLM_SEMANTIC_CACHE_ENABLED,
)

logger = logging.getLogger(__name__)

# LLMFallbackService (from llm_fallback folder — ported from LLM Fallback 3)
# Handles: HuggingFace → Gemini → OpenAI → Claude via litellm after Groq/RunPod fail
try:
    from app.llm_fallback.service import LLMFallbackService, build_default_fallback_chain
    _fallback_service = LLMFallbackService(
        cache_backend=LLM_CACHE_BACKEND,
        semantic_caching=str(LLM_SEMANTIC_CACHE_ENABLED).strip().lower() in {"1", "true", "yes", "on"},
    )
    _FALLBACK_SERVICE_AVAILABLE = True
    logger.info("LLMFallbackService loaded successfully")
except Exception as _fb_exc:
    _FALLBACK_SERVICE_AVAILABLE = False
    _fallback_service = None
    logger.warning(f"LLMFallbackService unavailable: {_fb_exc}")


def ensure_llm_configured() -> None:
    runpod_token = FIDEON_SECRET_KEY or RUNPOD_API_KEY
    runpod_ready = bool(runpod_token and (RUNPOD_GENERATE_URL or RUNPOD_OPENAI_COMPAT_URL))
    if any([GROQ_API_KEY, runpod_ready, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY]):
        return
    raise HTTPException(
        status_code=500,
        detail="No LLM provider configured. Set at least one of: GROQ_API_KEY, FIDEON_SECRET_KEY/RUNPOD_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY",
    )


def _collect_text_from_messages(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).upper()
        content = str(msg.get("content", ""))
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


async def _single_sse_stream(text: str, model_name: str) -> AsyncGenerator[bytes, None]:
    chunk = {
        "id": "chatcmpl-fallback",
        "object": "chat.completion.chunk",
        "model": model_name,
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
    yield b"data: [DONE]\n\n"


async def _openai_compatible_stream(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    client = httpx.AsyncClient(timeout=None)
    req = client.build_request(
        "POST",
        endpoint,
        headers=headers,
        json=payload,
    )
    resp = await client.send(req, stream=True)
    if resp.status_code >= 400:
        body = await resp.aread()
        await resp.aclose()
        await client.aclose()
        raise RuntimeError(f"{resp.status_code}: {body.decode('utf-8', errors='ignore')}")

    async def iterator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return 200, {"Content-Type": "text/event-stream"}, iterator()


def _clean_bearer_token(raw_token: str) -> str:
    token = (raw_token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _runpod_auth_headers(runpod_token: str) -> dict[str, str]:
    """
    Send both bearer and x-api-key headers for RunPod/proxy auth.
    Some gateway setups enforce x-api-key while others use Authorization.
    """
    return {
        "Authorization": f"Bearer {runpod_token}",
        "x-api-key": runpod_token,
        "Content-Type": "application/json",
    }


def _extract_runpod_text(data: dict[str, Any]) -> str:
    # Handle common response payload shapes from /generate style endpoints.
    direct_keys = ["response", "generated_text", "text", "output"]
    for key in direct_keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        text = first.get("text") if isinstance(first, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()

    data_value = data.get("data")
    if isinstance(data_value, dict):
        for key in direct_keys:
            value = data_value.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    raise RuntimeError("RunPod returned empty content")


async def _runpod_generate_text(payload: dict[str, Any], model_name: str) -> str:
    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)
    if not runpod_token:
        raise RuntimeError("RunPod token not configured")
    if not RUNPOD_GENERATE_URL:
        raise RuntimeError("RUNPOD_GENERATE_URL is not configured")

    prompt = _collect_text_from_messages(payload.get("messages", []))
    if not prompt:
        prompt = "Please help the user."

    # RunPod /generate endpoints vary between deployments (query params vs JSON body).
    # Try common request shapes in order for better local/VM compatibility.
    attempts = [
        {
            "params": {"prompt": prompt, "model": model_name},
            "json": None,
        },
        {
            "params": None,
            "json": {"prompt": prompt, "model": model_name},
        },
    ]
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=90) as client:
        for attempt in attempts:
            resp = await client.post(
                RUNPOD_GENERATE_URL,
                params=attempt["params"],
                json=attempt["json"],
                headers=_runpod_auth_headers(runpod_token),
            )
            if resp.status_code >= 400:
                errors.append(f"{resp.status_code}: {resp.text[:300]}")
                continue
            content_type = (resp.headers.get("content-type") or "").lower()
            if "application/json" in content_type:
                data = resp.json()
                return _extract_runpod_text(data)
            text = resp.text.strip()
            if text:
                return text
            errors.append("empty response body")
    raise RuntimeError(f"RunPod /generate failed across request formats: {' | '.join(errors)}")


async def _offline_fallback_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        prompt = _collect_text_from_messages(payload.get("messages", []))
    if not prompt:
        prompt = "Please help the user."
    if not RUNPOD_GENERATE_URL:
        raise RuntimeError("RUNPOD_GENERATE_URL is not configured")
    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)

    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Content-Type": "application/json"}
        if runpod_token:
            headers = _runpod_auth_headers(runpod_token)
        offline_resp = await client.post(
            RUNPOD_GENERATE_URL,
            json={"prompt": prompt},
            headers=headers,
        )
        if offline_resp.status_code >= 400:
            raise RuntimeError(f"{offline_resp.status_code}: {offline_resp.text}")

        content_type = (offline_resp.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            data = offline_resp.json()
            offline_text = _extract_runpod_text(data)
        else:
            offline_text = offline_resp.text.strip()

    if not offline_text:
        raise RuntimeError("offline-llm returned empty response")
    return 200, {"Content-Type": "text/event-stream"}, _single_sse_stream(offline_text, "offline-llm")


async def _gemini_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    merged = _collect_text_from_messages(messages)
    if not merged:
        merged = "Please help the user."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": merged}]}]}
    params = {"key": GEMINI_API_KEY}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, params=params, json=body, headers={"Content-Type": "application/json"})
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code}: {resp.text}")
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned empty content")
    return text


async def _openai_text(payload: dict[str, Any]) -> str:
    body = {**payload, "model": OPENAI_MODEL, "stream": False}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            json=body,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code}: {resp.text}")
        data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text:
        raise RuntimeError("OpenAI returned empty content")
    return text


async def _claude_text(payload: dict[str, Any]) -> str:
    src_messages = payload.get("messages", [])
    system_text = ""
    claude_messages: list[dict[str, Any]] = []
    for msg in src_messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_text = f"{system_text}\n{content}".strip()
            continue
        mapped_role = "assistant" if role == "assistant" else "user"
        claude_messages.append({"role": mapped_role, "content": str(content)})

    if not claude_messages:
        claude_messages = [{"role": "user", "content": "Please help the user."}]

    body: dict[str, Any] = {
        "model": CLAUDE_MODEL,
        "max_tokens": int(payload.get("max_tokens") or 1024),
        "messages": claude_messages,
    }
    if system_text:
        body["system"] = system_text

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            ANTHROPIC_MESSAGES_URL,
            json=body,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code}: {resp.text}")
        data = resp.json()

    content = data.get("content", [])
    text = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("type") == "text").strip()
    if not text:
        raise RuntimeError("Claude returned empty content")
    return text


async def llm_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    model_name = str(payload.get("model") or "")
    stream_payload = {**payload, "stream": True}
    errors: list[str] = []

    # Priority requested by user: Groq -> RunPod llama -> RunPod mistral -> Gemini -> OpenAI -> Claude
    if GROQ_API_KEY:
        try:
            groq_payload = {**stream_payload, "model": model_name or stream_payload.get("model")}
            status, headers, stream = await _openai_compatible_stream(GROQ_OPENAI_COMPAT_URL, GROQ_API_KEY, groq_payload)
            headers = {
                **headers,
                "x-llm-provider": "groq",
                "x-llm-model": str(groq_payload.get("model") or ""),
            }
            logger.info(f"LLM success provider=groq model={groq_payload.get('model')}")
            return status, headers, stream
        except Exception as exc:
            errors.append(f"groq: {exc}")

    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)
    if runpod_token and RUNPOD_GENERATE_URL:
        try:
            text = await _runpod_generate_text(payload, RUNPOD_MODEL_LLAMA)
            logger.info(f"LLM success provider=runpod_generate model={RUNPOD_MODEL_LLAMA}")
            return 200, {
                "Content-Type": "text/event-stream",
                "x-llm-provider": "runpod_generate",
                "x-llm-model": RUNPOD_MODEL_LLAMA,
            }, _single_sse_stream(text, RUNPOD_MODEL_LLAMA)
        except Exception as exc:
            errors.append(f"runpod-generate-llama: {exc}")

        try:
            text = await _runpod_generate_text(payload, RUNPOD_MODEL_MISTRAL)
            logger.info(f"LLM success provider=runpod_generate model={RUNPOD_MODEL_MISTRAL}")
            return 200, {
                "Content-Type": "text/event-stream",
                "x-llm-provider": "runpod_generate",
                "x-llm-model": RUNPOD_MODEL_MISTRAL,
            }, _single_sse_stream(text, RUNPOD_MODEL_MISTRAL)
        except Exception as exc:
            errors.append(f"runpod-generate-mistral: {exc}")

    if runpod_token and RUNPOD_OPENAI_COMPAT_URL:
        try:
            runpod_llama_payload = {**stream_payload, "model": RUNPOD_MODEL_LLAMA}
            status, headers, stream = await _openai_compatible_stream(
                RUNPOD_OPENAI_COMPAT_URL,
                runpod_token,
                runpod_llama_payload,
                extra_headers={"x-api-key": runpod_token},
            )
            headers = {
                **headers,
                "x-llm-provider": "runpod_openai_compat",
                "x-llm-model": RUNPOD_MODEL_LLAMA,
            }
            logger.info(f"LLM success provider=runpod_openai_compat model={RUNPOD_MODEL_LLAMA}")
            return status, headers, stream
        except Exception as exc:
            errors.append(f"runpod-llama: {exc}")

        try:
            runpod_mistral_payload = {**stream_payload, "model": RUNPOD_MODEL_MISTRAL}
            status, headers, stream = await _openai_compatible_stream(
                RUNPOD_OPENAI_COMPAT_URL,
                runpod_token,
                runpod_mistral_payload,
                extra_headers={"x-api-key": runpod_token},
            )
            headers = {
                **headers,
                "x-llm-provider": "runpod_openai_compat",
                "x-llm-model": RUNPOD_MODEL_MISTRAL,
            }
            logger.info(f"LLM success provider=runpod_openai_compat model={RUNPOD_MODEL_MISTRAL}")
            return status, headers, stream
        except Exception as exc:
            errors.append(f"runpod-mistral: {exc}")

    if str(OFFLINE_LLM_FALLBACK_ENABLED).strip().lower() in {"1", "true", "yes", "on"}:
        try:
            status, headers, stream = await _offline_fallback_stream(payload)
            headers = {
                **headers,
                "x-llm-provider": "offline-llm",
                "x-llm-model": "offline-llm",
            }
            logger.info("LLM success provider=offline-llm model=offline-llm")
            return status, headers, stream
        except Exception as offline_exc:
            errors.append(f"offline-llm: {offline_exc}")

    # ── LLMFallbackService chain (ported from LLM Fallback 3) ─────────────
    # Handles: HuggingFace → Gemini → OpenAI → Claude via litellm
    # Falls back to individual httpx calls if litellm is not installed.
    if _FALLBACK_SERVICE_AVAILABLE and _fallback_service is not None:
        try:
            fb_chain = build_default_fallback_chain()
            if fb_chain:
                fb_result = await _fallback_service.execute(
                    messages=payload.get("messages", []),
                    models=fb_chain,
                )
                if fb_result.success and fb_result.content:
                    logger.info(f"LLMFallbackService succeeded via {fb_result.model} "
                                f"(fallbacks={fb_result.fallback_count})")
                    return (
                        200,
                        {
                            "Content-Type": "text/event-stream",
                            "x-llm-provider": "litellm-fallback",
                            "x-llm-model": str(fb_result.model or ""),
                        },
                        _single_sse_stream(fb_result.content, fb_result.model),
                    )
                if fb_result.errors:
                    for e in fb_result.errors:
                        errors.append(f"litellm-fallback/{e}")
        except Exception as fb_exc:
            errors.append(f"litellm-fallback: {fb_exc}")
            logger.warning(f"LLMFallbackService chain error: {fb_exc}")
    else:
        # litellm not available — use direct httpx calls as before
        if GEMINI_API_KEY:
            try:
                text = await _gemini_text(payload)
                logger.info(f"LLM success provider=gemini model={GEMINI_MODEL}")
                return 200, {
                    "Content-Type": "text/event-stream",
                    "x-llm-provider": "gemini",
                    "x-llm-model": GEMINI_MODEL,
                }, _single_sse_stream(text, GEMINI_MODEL)
            except Exception as exc:
                errors.append(f"gemini: {exc}")

        if OPENAI_API_KEY:
            try:
                text = await _openai_text(payload)
                logger.info(f"LLM success provider=openai model={OPENAI_MODEL}")
                return 200, {
                    "Content-Type": "text/event-stream",
                    "x-llm-provider": "openai",
                    "x-llm-model": OPENAI_MODEL,
                }, _single_sse_stream(text, OPENAI_MODEL)
            except Exception as exc:
                errors.append(f"openai: {exc}")

        if ANTHROPIC_API_KEY:
            try:
                text = await _claude_text(payload)
                logger.info(f"LLM success provider=claude model={CLAUDE_MODEL}")
                return 200, {
                    "Content-Type": "text/event-stream",
                    "x-llm-provider": "claude",
                    "x-llm-model": CLAUDE_MODEL,
                }, _single_sse_stream(text, CLAUDE_MODEL)
            except Exception as exc:
                errors.append(f"claude: {exc}")

    # Preserve common UX status codes where possible.
    combined = " | ".join(errors) if errors else "No provider available"
    if any("429" in e for e in errors):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded across providers: {combined}")
    if any("402" in e for e in errors):
        raise HTTPException(status_code=402, detail=f"Payment required on provider chain: {combined}")
    raise HTTPException(status_code=500, detail=f"AI fallback chain failed: {combined}")
