"""
Natural language summary generation for ACORD extraction results.

Enabled via ACORD_NL_SUMMARY_ENABLED=true.
Uses whichever LLM endpoint is configured (RUNPOD_GENERATE_URL → chat endpoint fallback).
All failures are silently swallowed — the summary is always optional.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an insurance document analyst. Write a professional summary of this ACORD insurance form in plain prose paragraphs.

RULES (follow exactly):
- Write 3 to 5 paragraphs of plain prose — no bullet points, no numbered lists, no headings
- Use the exact names, dates, policy numbers, phone numbers, and addresses from the document
- Cover each topic only once: who the applicant is and what form this is; premises and locations; business operations; prior carriers, premiums, loss history; contacts and agency details
- Skip any topic that has no data
- Stop writing immediately after the final paragraph

DOCUMENT FIELDS:
{fields_text}

Write the summary now:"""

_GARBAGE_VALUES = {"$", "</b>", "<b>", "", "-", "none", "n/a", "n/a.", "null", "undefined"}
_SKIP_KEY_PREFIXES = ("applicable_in_",)


def _to_label(key: str) -> str:
    return key.replace("_", " ").title()


def _fields_to_readable_text(extracted: dict[str, Any]) -> str:
    """
    Flatten nested extracted JSON into simple "Label: value" lines.
    This prevents the LLM from seeing JSON structure and defaulting to
    bullet-point enumeration of each key.
    """
    lines: list[str] = []

    def _emit(value: Any, prefix: str) -> None:
        if value is None or value == "":
            return
        if isinstance(value, dict):
            for k, v in value.items():
                if k.startswith("_"):
                    continue
                child_label = f"{prefix} - {_to_label(k)}" if prefix else _to_label(k)
                _emit(v, child_label)
        elif isinstance(value, list):
            if not value:
                return
            all_primitive = all(not isinstance(item, (dict, list)) for item in value)
            if all_primitive:
                joined = ", ".join(str(v) for v in value if v is not None)
                if joined.strip():
                    lines.append(f"{prefix}: {joined}")
            else:
                for idx, item in enumerate(value, 1):
                    _emit(item, f"{prefix} {idx}")
        else:
            s = str(value).strip()
            if s and s.lower() not in _GARBAGE_VALUES:
                lines.append(f"{prefix}: {s}")

    for key, value in extracted.items():
        if any(key.startswith(p) for p in _SKIP_KEY_PREFIXES):
            continue
        if isinstance(value, str) and value.strip().lower() in _GARBAGE_VALUES:
            continue
        _emit(value, _to_label(key))

    return "\n".join(lines)


async def generate_nl_summary(extracted: dict[str, Any], raw_text: str) -> Optional[str]:
    """
    Returns a natural language narrative of the ACORD document, or None when:
    - ACORD_NL_SUMMARY_ENABLED is not set to true
    - No LLM endpoint is configured
    - The LLM call fails for any reason
    """
    enabled = os.getenv("ACORD_NL_SUMMARY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None

    fields_text = _fields_to_readable_text(extracted)
    # Cap so prompt stays within model context; raw text is secondary reference
    fields_snippet = fields_text[:6000]
    prompt = _PROMPT_TEMPLATE.format(fields_text=fields_snippet)

    offline_url = (os.getenv("RUNPOD_GENERATE_URL") or os.getenv("OFFLINE_LLM_GENERATE_URL") or "").strip()
    chat_url = (os.getenv("RUNPOD_OPENAI_COMPAT_URL") or os.getenv("OPENAI_CHAT_COMPLETIONS_URL") or "").strip()
    token = (os.getenv("OFFLINE_LLM_AUTH_TOKEN") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OFFLINE_LLM_MODEL_NAME") or os.getenv("OPENAI_MODEL") or "").strip()

    if not offline_url and not chat_url:
        return None

    headers = {"Content-Type": "application/json"}
    if token:
        tok = token[7:].strip() if token.lower().startswith("bearer ") else token
        headers["Authorization"] = f"Bearer {tok}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if offline_url:
                resp = await client.post(
                    offline_url,
                    headers=headers,
                    json={
                        "prompt": prompt,
                        "model": model or "default",
                        "max_new_tokens": 900,
                        "temperature": 0.1,
                        "raw": True,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("text")
                    or data.get("generated_text")
                    or data.get("response")
                    or ""
                )
            else:
                resp = await client.post(
                    chat_url,
                    headers=headers,
                    json={
                        "model": model or "default",
                        "messages": [
                            {"role": "system", "content": "You are a senior insurance document analyst."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 900,
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        summary = (text or "").strip()
        return summary if len(summary) > 100 else None

    except Exception as exc:
        logger.warning(
            "ACORD[nl_summary] generation failed (non-fatal): %s — "
            "check RUNPOD_GENERATE_URL=%s is reachable and pod is running updated server.py",
            exc, offline_url or chat_url,
        )
        return None
