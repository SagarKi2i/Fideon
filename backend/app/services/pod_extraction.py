from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from fastapi import UploadFile

from app.core.supabase import postgrest_get
from app.core.config import (
    DEFAULT_PRIMARY_LLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_CHAT_COMPLETIONS_URL,
    OPENAI_MODEL,
    OFFLINE_LLM_GENERATE_URL,
    OFFLINE_LLM_AUTH_TOKEN,
    OFFLINE_LLM_MODEL_NAME,
    OFFLINE_LLM_HTTP_TIMEOUT_SECONDS,
)
from Models.acord_form_understanding import AcordFormSummary
from Models.acord_form_understanding.extraction_pipeline import is_vl_model_id
from app.services.vectorstore_ingestion import ingest_text_into_vectorstore

logger = logging.getLogger("fideon.pod_extraction")

_ADAPTER_CACHE: dict[str, tuple[Any, Any]] = {}


@dataclass(frozen=True)
class PodExtractionResult:
    raw_text: str
    extracted_json: Dict[str, Any]
    overall_confidence: float
    doc_id: str


async def _load_pod_agent_and_domain(pod_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    agents = await postgrest_get(
        "agent_catalog",
        f"id=eq.{quote(pod_id, safe='')}&is_active=eq.true&select=*",
    )
    if not agents:
        raise ValueError(f"Pod agent not found or inactive: {pod_id}")
    agent = agents[0]

    domain_id = agent.get("domain_id")
    if not domain_id:
        raise ValueError(f"Pod agent missing domain_id: {pod_id}")

    domains = await postgrest_get(
        "domain_catalog",
        f"id=eq.{quote(str(domain_id), safe='')}&is_active=eq.true&select=*",
    )
    if not domains:
        raise ValueError(f"Domain not found or inactive for pod_id={pod_id}")
    domain = domains[0]

    return agent, domain


def _pod_collection_name(agent: dict[str, Any], domain: dict[str, Any]) -> str:
    # Same resolution strategy as LLM/RAG generator.
    return agent.get("rag_collection_override") or domain.get("rag_collection") or f"{domain['id']}_index"


def _extract_doc_id(file: UploadFile, pod_id: str) -> str:
    filename = (file.filename or "").strip()
    if not filename:
        return f"{pod_id}-upload"
    return filename.lower().rsplit(".", 1)[0]


async def _read_text_for_generic_pods(file: UploadFile) -> str:
    """
    For v1 we reuse the existing ACORD route's file-to-text handler.
    This keeps the extraction workflow consistent across pods while we
    gradually refactor file parsing into standalone utilities.
    """
    from app.routes.acord import _read_text_from_file  # local import to avoid startup cycles

    # _read_text_from_file consumes the stream; it expects UploadFile.
    return await _read_text_from_file(file)


def _extraction_strategy(agent: dict[str, Any], pod_id: str) -> str:
    tools = agent.get("tools") or {}
    if isinstance(tools, dict):
        return str(tools.get("extraction_strategy") or "").strip() or (
            "acord_form_understanding" if pod_id == "acord_form_understanding" else "generic_structured_llm"
        )
    return "acord_form_understanding" if pod_id == "acord_form_understanding" else "generic_structured_llm"


def _parse_json_candidate(content: str) -> Optional[Dict[str, Any]]:
    if not content or not content.strip():
        return None
    s = content.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


def _schema_compatible(schema: Any, value: Any, *, allow_extra_fields: bool = True) -> bool:
    """
    Lightweight schema-shape validation.
    - Dict schema => value must be dict; unknown keys rejected except "extra_fields" when allowed.
    - List schema with one exemplar item => each list item validated against exemplar.
    - Scalar schema => any scalar accepted (type map strings are treated as hints only).
    """
    if schema in (None, "", {}):
        return True
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            return False
        allowed_keys = set(schema.keys())
        for k in value.keys():
            if k in allowed_keys:
                continue
            if allow_extra_fields and k == "extra_fields":
                continue
            return False
        for k, child_schema in schema.items():
            if k in value and not _schema_compatible(child_schema, value[k], allow_extra_fields=allow_extra_fields):
                return False
        return True
    if isinstance(schema, list):
        if not isinstance(value, list):
            return False
        if not schema:
            return True
        exemplar = schema[0]
        return all(_schema_compatible(exemplar, item, allow_extra_fields=allow_extra_fields) for item in value)
    return True


def _build_prompt(*, output_schema: dict[str, Any], raw_text: str, extraction_hint: Optional[str]) -> str:
    hint_line = f"\n\nUSER_HINT: {extraction_hint.strip()}" if extraction_hint else ""
    return f"""OUTPUT_SCHEMA (JSON template or type map):
{json.dumps(output_schema, indent=2)}
{hint_line}

INSTRUCTIONS:
1. Return ONLY valid JSON.
2. JSON MUST match the keys/structure of the OUTPUT_SCHEMA.
3. Never fabricate; use null for missing/blank values.
4. If extra fields exist in the data but are not in the schema, put them into "extra_fields".

TEXT TO EXTRACT:
{raw_text}
"""


def _extract_text_from_generate_response(data: dict[str, Any]) -> str:
    for key in ("response", "generated_text", "text", "output"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        txt = first.get("text") if isinstance(first, dict) else None
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
    return ""


def _is_small_model_name(model_name: str) -> bool:
    m = (model_name or "").strip().lower()
    if not m:
        return False
    if "llama-8b" in m or "llama_8b" in m:
        return True
    if "8b" in m and "llama" in m:
        return True
    if "meta-llama" in m and "8b" in m:
        return True
    if ("llama-3" in m or "llama3" in m) and "8b" in m:
        return True
    return False


def _split_text_windows(text: str, *, window_chars: int, stride_chars: int) -> list[str]:
    src = (text or "").strip()
    if not src:
        return []
    if len(src) <= window_chars:
        return [src]
    windows: list[str] = []
    start = 0
    while start < len(src):
        chunk = src[start : start + window_chars].strip()
        if chunk:
            windows.append(chunk)
        if start + window_chars >= len(src):
            break
        start += stride_chars
    return windows


def _merge_json_values(current: Any, incoming: Any) -> Any:
    if current in (None, "", [], {}):
        return incoming
    if incoming in (None, "", [], {}):
        return current
    if isinstance(current, dict) and isinstance(incoming, dict):
        out = dict(current)
        for k, v in incoming.items():
            out[k] = _merge_json_values(out.get(k), v) if k in out else v
        return out
    if isinstance(current, list) and isinstance(incoming, list):
        seen: set[str] = set()
        merged: list[Any] = []
        for item in (current + incoming):
            sig = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
            if sig in seen:
                continue
            seen.add(sig)
            merged.append(item)
        return merged
    return current


async def _latest_completed_adapter_dir(pod_id: str) -> Optional[str]:
    rows = await postgrest_get(
        "pod_training_jobs",
        (
            "select=output_dir,finished_at,status"
            f"&pod_id=eq.{quote(pod_id, safe='')}"
            "&status=eq.completed"
            "&order=finished_at.desc,created_at.desc"
            "&limit=1"
        ),
    )
    if not rows:
        return None
    path = str(rows[0].get("output_dir") or "").strip()
    if not path:
        return None
    return path


async def _local_adapter_extract(
    *,
    pod_id: str,
    output_schema: dict[str, Any],
    system_prompt: str,
    raw_text: str,
    extraction_hint: Optional[str],
) -> Optional[Dict[str, Any]]:
    use_local = (os.getenv("POD_EXTRACTION_USE_LOCAL_ADAPTER") or "false").strip().lower() in {"1", "true", "yes", "on"}
    if not use_local:
        return None
    adapter_dir = await _latest_completed_adapter_dir(pod_id)
    if not adapter_dir:
        return None
    adapter_path = Path(adapter_dir)
    if not adapter_path.exists():
        logger.warning("Pod adapter path not found; falling back to API extraction: %s", adapter_path)
        return None

    base_model = (os.getenv("POD_ADAPTER_BASE_MODEL") or "").strip()
    if not base_model:
        logger.warning("POD_ADAPTER_BASE_MODEL not configured; cannot load local adapter. Falling back to API.")
        return None

    load_in_4bit = (os.getenv("POD_ADAPTER_LOAD_IN_4BIT") or "true").strip().lower() in {"1", "true", "yes", "on"}
    local_files_only = (os.getenv("POD_ADAPTER_LOCAL_FILES_ONLY") or "true").strip().lower() in {"1", "true", "yes", "on"}
    max_new_tokens = int(os.getenv("POD_ADAPTER_MAX_NEW_TOKENS", "1024"))

    cache_key = f"{base_model}|{adapter_path.resolve()}"
    if cache_key not in _ADAPTER_CACHE:
        from fine_tuning.inference import load_model_for_inference

        model, tokenizer = await asyncio.to_thread(
            load_model_for_inference,
            base_model,
            str(adapter_path),
            load_in_4bit=load_in_4bit,
            use_auth_token=False,
            local_files_only=local_files_only,
        )
        _ADAPTER_CACHE[cache_key] = (model, tokenizer)

    model, tokenizer = _ADAPTER_CACHE[cache_key]
    from fine_tuning.inference import generate_with_verification

    prompt = _build_prompt(output_schema=output_schema, raw_text=raw_text, extraction_hint=extraction_hint)
    answer = await asyncio.to_thread(
        generate_with_verification,
        model,
        tokenizer,
        f"{system_prompt}\n\n{prompt}",
        "",
        max_new_tokens=max_new_tokens,
        temperature=0.0,
        verification_prompt=(
            "You must return ONLY valid JSON that matches OUTPUT_SCHEMA. "
            "Fix invalid JSON and remove unsupported keys/claims."
        ),
        max_verification_tokens=300,
    )
    parsed = _parse_json_candidate(answer)
    if not parsed:
        return None
    if not _schema_compatible(output_schema, parsed):
        return None
    logger.info("Pod extraction used local fine-tuned adapter: pod_id=%s adapter=%s", pod_id, adapter_path)
    return parsed


async def _openai_structured_extract_with_retries(
    *,
    pod_id: str,
    output_schema: dict[str, Any],
    system_prompt: str,
    raw_text: str,
    extraction_hint: Optional[str],
) -> Optional[Dict[str, Any]]:
    api_key = (OPENAI_API_KEY or "").strip()
    url = (OPENAI_CHAT_COMPLETIONS_URL or "").strip() or "https://api.openai.com/v1/chat/completions"
    model = (OPENAI_MODEL or DEFAULT_PRIMARY_LLM_MODEL).strip()
    strict_llama8b_only = (os.getenv("POD_STRICT_LLAMA8B_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"})
    offline_url = (OFFLINE_LLM_GENERATE_URL or "").strip()
    offline_model = (OFFLINE_LLM_MODEL_NAME or "").strip() or model
    offline_token = (OFFLINE_LLM_AUTH_TOKEN or "").strip()
    runpod_chat_url = (os.getenv("RUNPOD_OPENAI_COMPAT_URL") or "").strip()
    api_key_stripped = (api_key or "").strip()
    use_offline = bool(offline_url) and (strict_llama8b_only or not api_key_stripped)
    if strict_llama8b_only and not offline_url:
        raise RuntimeError("POD_STRICT_LLAMA8B_ONLY is enabled but OFFLINE_LLM_GENERATE_URL is not configured")
    if not use_offline and not api_key_stripped and not offline_url:
        raise RuntimeError("No structured extraction provider configured for pods")

    max_attempts = int(os.getenv("POD_EXTRACTION_MAX_RETRIES", "3"))
    small_model = _is_small_model_name(model) or _is_small_model_name(offline_model) or strict_llama8b_only
    use_multi_pass = small_model and (os.getenv("POD_EXTRACTION_MULTI_PASS", "true").strip().lower() in {"1", "true", "yes", "on"})
    window_chars = int(os.getenv("POD_EXTRACTION_WINDOW_CHARS", "7000" if small_model else "20000"))
    stride_chars = int(os.getenv("POD_EXTRACTION_WINDOW_STRIDE_CHARS", "5000" if small_model else "15000"))
    max_tokens = int(os.getenv("POD_EXTRACTION_MAX_TOKENS", "1200" if small_model else "4096"))
    max_new_tokens = int(os.getenv("POD_EXTRACTION_MAX_NEW_TOKENS_SMALL", "768")) if small_model else max_tokens
    windows = _split_text_windows(raw_text, window_chars=window_chars, stride_chars=stride_chars) if use_multi_pass else [raw_text]
    if not windows:
        windows = [raw_text]

    merged: dict[str, Any] = {}
    any_success = False

    headers_offline = {"Content-Type": "application/json"}
    if offline_token:
        tok = offline_token[7:].strip() if offline_token.lower().startswith("bearer ") else offline_token
        headers_offline["Authorization"] = f"Bearer {tok}"

    timeout = (
        OFFLINE_LLM_HTTP_TIMEOUT_SECONDS
        if use_offline
        else 90.0
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        for idx, window_text in enumerate(windows, start=1):
            correction = ""
            prompt_base = _build_prompt(output_schema=output_schema, raw_text=window_text, extraction_hint=extraction_hint)
            parsed_for_window: Optional[Dict[str, Any]] = None
            for attempt in range(1, max_attempts + 1):
                correction_block = f"\n\nPREVIOUS_OUTPUT_ISSUE:\n{correction}\nPlease fix and return only valid JSON." if correction else ""
                if use_offline:
                    prompt = f"{system_prompt}\n\n{prompt_base}{correction_block}"
                    # Qwen2.5-VL and other vision models must use OpenAI-compatible chat (vLLM), not /generate.
                    if runpod_chat_url and is_vl_model_id(offline_model):
                        resp = await client.post(
                            runpod_chat_url,
                            headers=headers_offline,
                            json={
                                "model": offline_model,
                                "stream": False,
                                "temperature": 0.0,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": prompt},
                                ],
                                "max_tokens": max_new_tokens,
                            },
                        )
                    else:
                        resp = await client.post(
                            offline_url,
                            headers=headers_offline,
                            json={
                                "prompt": prompt,
                                "model": offline_model,
                                "max_new_tokens": max_new_tokens,
                                "temperature": 0.0,
                            },
                        )
                else:
                    payload = {
                        "model": model,
                        "stream": False,
                        "temperature": 0,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{prompt_base}{correction_block}"},
                        ],
                        "max_tokens": max_tokens,
                    }
                    headers_chat = {"Content-Type": "application/json"}
                    if api_key_stripped:
                        headers_chat["Authorization"] = f"Bearer {api_key_stripped}"
                    resp = await client.post(
                        url,
                        headers=headers_chat,
                        json=payload,
                    )
                if resp.status_code >= 400:
                    logger.warning(
                        "Pod generic extraction failed pod_id=%s window=%s/%s attempt=%s/%s: %s %s",
                        pod_id,
                        idx,
                        len(windows),
                        attempt,
                        max_attempts,
                        resp.status_code,
                        (resp.text or "")[:300],
                    )
                    correction = f"HTTP error {resp.status_code}; ensure JSON-only output."
                    continue

                content_type = (resp.headers.get("content-type") or "").lower()
                if "application/json" in content_type:
                    data = resp.json()
                    used_vl_chat = use_offline and runpod_chat_url and is_vl_model_id(offline_model)
                    content = (
                        (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "")
                        if used_vl_chat
                        else (
                            _extract_text_from_generate_response(data)
                            if use_offline
                            else (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "")
                        )
                    )
                else:
                    content = (resp.text or "").strip()
                parsed = _parse_json_candidate(content)
                if not parsed:
                    correction = "Output was not valid JSON."
                    continue
                if not _schema_compatible(output_schema, parsed):
                    correction = (
                        "JSON shape mismatch with OUTPUT_SCHEMA. "
                        "Do not add unknown top-level keys except extra_fields, and keep nested structures aligned."
                    )
                    continue
                parsed_for_window = parsed
                break

            if parsed_for_window:
                any_success = True
                merged = _merge_json_values(merged, parsed_for_window)

    if any_success:
        if len(windows) > 1:
            logger.info("Pod extraction multi-pass merge complete: pod_id=%s windows=%s", pod_id, len(windows))
        return merged if isinstance(merged, dict) else None
    return None


async def _generic_structured_extract(
    *,
    pod_id: str,
    raw_text: str,
    agent: dict[str, Any],
    extraction_hint: Optional[str] = None,
) -> tuple[Dict[str, Any], float]:
    output_schema = agent.get("output_schema") or {}
    system_prompt = agent.get("system_prompt") or "You are a structured extraction engine."
    local_result = await _local_adapter_extract(
        pod_id=pod_id,
        output_schema=output_schema,
        system_prompt=system_prompt,
        raw_text=raw_text,
        extraction_hint=extraction_hint,
    )
    if local_result:
        return local_result, 0.95

    parsed = await _openai_structured_extract_with_retries(
        pod_id=pod_id,
        output_schema=output_schema,
        system_prompt=system_prompt,
        raw_text=raw_text,
        extraction_hint=extraction_hint,
    )
    if not parsed:
        return {}, 0.0
    return parsed, 0.9


async def extract_and_prepare_pod_run(
    *,
    pod_id: str,
    file: UploadFile,
    extraction_hint: Optional[str] = None,
    ingest_to_vectorstore: bool = True,
) -> PodExtractionResult:
    """
    Extract raw_text + extracted_json for a pod and optionally ingest raw_text into pgvector.
    """
    agent, domain = await _load_pod_agent_and_domain(pod_id)
    collection_name = _pod_collection_name(agent, domain)
    strategy = _extraction_strategy(agent, pod_id)
    doc_id = _extract_doc_id(file, pod_id)

    # --- Special-case ACORD for now (reuses existing high-fidelity extraction) ---
    if strategy == "acord_form_understanding":
        # Reuse existing ACORD extraction chain from the current route implementation.
        from app.routes.acord import _extract_summary_from_file

        summary: AcordFormSummary = await _extract_summary_from_file(
            file,
            form_type_hint=extraction_hint,
        )
        raw_text = summary.raw_text or ""
        extracted = summary.model_dump(mode="json", exclude_none=True)
        extracted.pop("raw_text", None)
        overall_confidence = float(summary.overall_confidence or 0.0)

        if ingest_to_vectorstore and raw_text.strip():
            ingest_text_into_vectorstore(
                collection_name=collection_name,
                doc_id=doc_id,
                text=raw_text,
                pod_id=pod_id,
                source="acord-upload",
            )
        return PodExtractionResult(
            raw_text=raw_text,
            extracted_json=extracted,
            overall_confidence=overall_confidence,
            doc_id=doc_id,
        )

    # --- Generic pod extraction via structured LLM ---
    raw_text = await _read_text_for_generic_pods(file)
    extracted_json, overall_confidence = await _generic_structured_extract(
        pod_id=pod_id,
        raw_text=raw_text,
        agent=agent,
        extraction_hint=extraction_hint,
    )

    if ingest_to_vectorstore and raw_text.strip():
        ingest_text_into_vectorstore(
            collection_name=collection_name,
            doc_id=doc_id,
            text=raw_text,
            pod_id=pod_id,
            source="pod-upload",
        )

    return PodExtractionResult(
        raw_text=raw_text,
        extracted_json=extracted_json,
        overall_confidence=overall_confidence,
        doc_id=doc_id,
    )


async def extract_and_prepare_pod_reextract_from_raw_text(
    *,
    pod_id: str,
    raw_text: str,
    extraction_hint: Optional[str] = None,
) -> tuple[Dict[str, Any], float]:
    """
    Re-run extraction from stored raw_text (no re-ingest into pgvector by default).
    """
    agent, _domain = await _load_pod_agent_and_domain(pod_id)
    strategy = _extraction_strategy(agent, pod_id)

    if strategy == "acord_form_understanding":
        from app.routes.acord import _extract_summary_from_raw_text

        summary: AcordFormSummary = await _extract_summary_from_raw_text(
            raw_text=raw_text,
            form_type_hint=extraction_hint,
        )
        extracted = summary.model_dump(mode="json", exclude_none=True)
        extracted.pop("raw_text", None)
        return extracted, float(summary.overall_confidence or 0.0)

    extracted_json, overall_confidence = await _generic_structured_extract(
        pod_id=pod_id,
        raw_text=raw_text,
        agent=agent,
        extraction_hint=extraction_hint,
    )
    return extracted_json, overall_confidence

