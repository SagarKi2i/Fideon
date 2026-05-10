import json
import logging
from typing import Any, AsyncGenerator

import httpx
from fastapi import HTTPException

from app.core.resilience import runpod_retry, runpod_circuit_breaker
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
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_SSE = "text/event-stream"
DEFAULT_USER_PROMPT = "Please help the user."

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


def _sse_response_headers(provider: str, model: str) -> dict[str, str]:
    return {
        "Content-Type": CONTENT_TYPE_SSE,
        "x-llm-provider": provider,
        "x-llm-model": model,
    }


async def _openai_compatible_stream(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": CONTENT_TYPE_JSON,
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

    return 200, {"Content-Type": CONTENT_TYPE_SSE}, iterator()


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
        "Content-Type": CONTENT_TYPE_JSON,
    }


def _first_non_empty_text(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _text_from_choices(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not (isinstance(choices, list) and choices):
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message", {}) if isinstance(first, dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    text = first.get("text") if isinstance(first, dict) else None
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def _extract_runpod_text(data: dict[str, Any]) -> str:
    direct_keys = ["response", "generated_text", "text", "output"]
    for candidate in (
        _first_non_empty_text(data, direct_keys),
        _text_from_choices(data),
        _first_non_empty_text(data.get("data", {}) if isinstance(data.get("data"), dict) else {}, direct_keys),
    ):
        if candidate:
            return candidate
    raise RuntimeError("RunPod returned empty content")


@runpod_retry
async def _runpod_generate_text(payload: dict[str, Any], model_name: str) -> str:
    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)
    if not runpod_token:
        raise RuntimeError("RunPod token not configured")
    if not RUNPOD_GENERATE_URL:
        raise RuntimeError("RUNPOD_GENERATE_URL is not configured")

    prompt = _collect_text_from_messages(payload.get("messages", []))
    if not prompt:
        prompt = DEFAULT_USER_PROMPT

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
            if CONTENT_TYPE_JSON in content_type:
                data = resp.json()
                return _extract_runpod_text(data)
            text = resp.text.strip()
            if text:
                return text
            errors.append("empty response body")
    raise RuntimeError(f"RunPod /generate failed across request formats: {' | '.join(errors)}")


@runpod_retry
async def _offline_fallback_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    # W2: Check circuit breaker before hitting RunPod.
    runpod_circuit_breaker.before_call()
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        prompt = _collect_text_from_messages(payload.get("messages", []))
    if not prompt:
        prompt = DEFAULT_USER_PROMPT
    if not RUNPOD_GENERATE_URL:
        raise RuntimeError("RUNPOD_GENERATE_URL is not configured")
    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)

    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Content-Type": CONTENT_TYPE_JSON}
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
        if CONTENT_TYPE_JSON in content_type:
            data = offline_resp.json()
            offline_text = _extract_runpod_text(data)
        else:
            offline_text = offline_resp.text.strip()

    if not offline_text:
        raise RuntimeError("offline-llm returned empty response")
    return 200, {"Content-Type": CONTENT_TYPE_SSE}, _single_sse_stream(offline_text, "offline-llm")


async def _gemini_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    merged = _collect_text_from_messages(messages)
    if not merged:
        merged = DEFAULT_USER_PROMPT

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": merged}]}]}
    params = {"key": GEMINI_API_KEY}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, params=params, json=body, headers={"Content-Type": CONTENT_TYPE_JSON})
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
                "Content-Type": CONTENT_TYPE_JSON,
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
        claude_messages = [{"role": "user", "content": DEFAULT_USER_PROMPT}]

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
                "Content-Type": CONTENT_TYPE_JSON,
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


async def _try_groq_stream(stream_payload: dict[str, Any], model_name: str) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    groq_payload = {**stream_payload, "model": model_name or stream_payload.get("model")}
    status, headers, stream = await _openai_compatible_stream(GROQ_OPENAI_COMPAT_URL, GROQ_API_KEY, groq_payload)
    logger.info(f"LLM success provider=groq model={groq_payload.get('model')}")
    return status, {**headers, **_sse_response_headers("groq", str(groq_payload.get("model") or ""))}, stream


async def _try_runpod_generate_stream(payload: dict[str, Any], model_name: str) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    text = await _runpod_generate_text(payload, model_name)
    logger.info(f"LLM success provider=runpod_generate model={model_name}")
    return 200, _sse_response_headers("runpod_generate", model_name), _single_sse_stream(text, model_name)


async def _try_runpod_openai_compat_stream(
    stream_payload: dict[str, Any],
    runpod_token: str,
    model_name: str,
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    runpod_payload = {**stream_payload, "model": model_name}
    status, headers, stream = await _openai_compatible_stream(
        RUNPOD_OPENAI_COMPAT_URL,
        runpod_token,
        runpod_payload,
        extra_headers={"x-api-key": runpod_token},
    )
    logger.info(f"LLM success provider=runpod_openai_compat model={model_name}")
    return status, {**headers, **_sse_response_headers("runpod_openai_compat", model_name)}, stream


async def _try_offline_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    status, headers, stream = await _offline_fallback_stream(payload)
    logger.info("LLM success provider=offline-llm model=offline-llm")
    return status, {**headers, **_sse_response_headers("offline-llm", "offline-llm")}, stream


async def _try_litellm_fallback_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]] | None:
    if not (_FALLBACK_SERVICE_AVAILABLE and _fallback_service is not None):
        return None
    fb_chain = build_default_fallback_chain()
    if not fb_chain:
        return None
    fb_result = await _fallback_service.execute(messages=payload.get("messages", []), models=fb_chain)
    if not (fb_result.success and fb_result.content):
        if fb_result.errors:
            raise RuntimeError(" | ".join(fb_result.errors))
        return None
    logger.info(f"LLMFallbackService succeeded via {fb_result.model} (fallbacks={fb_result.fallback_count})")
    return 200, _sse_response_headers("litellm-fallback", str(fb_result.model or "")), _single_sse_stream(
        fb_result.content, fb_result.model
    )


async def _try_direct_provider_stream(payload: dict[str, Any], provider: str) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    if provider == "gemini":
        text = await _gemini_text(payload)
        logger.info(f"LLM success provider=gemini model={GEMINI_MODEL}")
        return 200, _sse_response_headers("gemini", GEMINI_MODEL), _single_sse_stream(text, GEMINI_MODEL)
    if provider == "openai":
        text = await _openai_text(payload)
        logger.info(f"LLM success provider=openai model={OPENAI_MODEL}")
        return 200, _sse_response_headers("openai", OPENAI_MODEL), _single_sse_stream(text, OPENAI_MODEL)
    text = await _claude_text(payload)
    logger.info(f"LLM success provider=claude model={CLAUDE_MODEL}")
    return 200, _sse_response_headers("claude", CLAUDE_MODEL), _single_sse_stream(text, CLAUDE_MODEL)


async def _recorded_attempt(label: str, errors: list[str], func):
    try:
        return await func()
    except Exception as exc:
        errors.append(f"{label}: {exc}")
        return None


async def _first_successful_attempt(
    attempts: list[tuple[str, Any]],
    errors: list[str],
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]] | None:
    for label, attempt_fn in attempts:
        result = await _recorded_attempt(label, errors, attempt_fn)
        if result:
            return result
    return None


async def _attempt_primary_chain(
    payload: dict[str, Any],
    stream_payload: dict[str, Any],
    model_name: str,
    runpod_token: str,
    errors: list[str],
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]] | None:
    if GROQ_API_KEY:
        result = await _recorded_attempt("groq", errors, lambda: _try_groq_stream(stream_payload, model_name))
        if result:
            return result

    if runpod_token and RUNPOD_GENERATE_URL:
        runpod_generate_attempts = [
            ("runpod-generate-llama", lambda: _try_runpod_generate_stream(payload, RUNPOD_MODEL_LLAMA)),
            ("runpod-generate-mistral", lambda: _try_runpod_generate_stream(payload, RUNPOD_MODEL_MISTRAL)),
        ]
        result = await _first_successful_attempt(runpod_generate_attempts, errors)
        if result:
            return result

    if runpod_token and RUNPOD_OPENAI_COMPAT_URL:
        runpod_compat_attempts = [
            (
                "runpod-llama",
                lambda: _try_runpod_openai_compat_stream(stream_payload, runpod_token, RUNPOD_MODEL_LLAMA),
            ),
            (
                "runpod-mistral",
                lambda: _try_runpod_openai_compat_stream(stream_payload, runpod_token, RUNPOD_MODEL_MISTRAL),
            ),
        ]
        result = await _first_successful_attempt(runpod_compat_attempts, errors)
        if result:
            return result

    if str(OFFLINE_LLM_FALLBACK_ENABLED).strip().lower() in {"1", "true", "yes", "on"}:
        result = await _recorded_attempt("offline-llm", errors, lambda: _try_offline_stream(payload))
        if result:
            return result
    return None


async def _attempt_direct_http_chain(
    payload: dict[str, Any],
    errors: list[str],
) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]] | None:
    if GEMINI_API_KEY:
        result = await _recorded_attempt("gemini", errors, lambda: _try_direct_provider_stream(payload, "gemini"))
        if result:
            return result
    if OPENAI_API_KEY:
        result = await _recorded_attempt("openai", errors, lambda: _try_direct_provider_stream(payload, "openai"))
        if result:
            return result
    if ANTHROPIC_API_KEY:
        result = await _recorded_attempt("claude", errors, lambda: _try_direct_provider_stream(payload, "claude"))
        if result:
            return result
    return None


async def llm_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    model_name = str(payload.get("model") or "")
    stream_payload = {**payload, "stream": True}
    errors: list[str] = []

    runpod_token = _clean_bearer_token(FIDEON_SECRET_KEY or RUNPOD_API_KEY)
    primary_result = await _attempt_primary_chain(payload, stream_payload, model_name, runpod_token, errors)
    if primary_result:
        return primary_result

    fallback_result = await _recorded_attempt("litellm-fallback", errors, lambda: _try_litellm_fallback_stream(payload))
    if fallback_result:
        return fallback_result

    if not (_FALLBACK_SERVICE_AVAILABLE and _fallback_service is not None):
        direct_result = await _attempt_direct_http_chain(payload, errors)
        if direct_result:
            return direct_result

    combined = " | ".join(errors) if errors else "No provider available"
    if any("429" in e for e in errors):
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded across providers: {combined}")
    if any("402" in e for e in errors):
        raise HTTPException(status_code=402, detail=f"Payment required on provider chain: {combined}")
    raise HTTPException(status_code=500, detail=f"AI fallback chain failed: {combined}")
