"""
Natural language summary generation for ACORD extraction results.

Enabled via ACORD_NL_SUMMARY_ENABLED=true.
Uses whichever LLM endpoint is configured (OFFLINE_LLM_GENERATE_URL → chat endpoint fallback).
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
You are a senior insurance document analyst. You have been given the structured fields extracted from an ACORD insurance form and the raw document text. Write a thorough, professional natural language summary that a claims adjuster or broker could use to understand the document at a glance.

STRICT RULES:
- Write in flowing paragraphs only — no bullet points, no numbered lists, no headings, no JSON, no markdown
- Cover every section that has data: named insured and address, producer/agent, insurers, policy numbers, effective and expiration dates, each coverage type with its exact limits and deductibles, additional insureds, certificate holders, special conditions, and cancellation provisions
- Use exact dollar figures as written on the form (e.g. "$1,000,000" or "$2,000,000 aggregate")
- If a field is truly blank or absent, omit it — never write "not provided" or "N/A"
- Do NOT reproduce raw OCR text verbatim — synthesise the information into professional prose
- Write at least 5 paragraphs: (1) parties and purpose, (2) general liability coverage, (3) auto and workers comp / employers liability, (4) umbrella / excess and any other coverages, (5) certificate holder, additional insured status, and special provisions
- If a coverage section has no data, skip that paragraph entirely
- Tone: factual, precise, professional

EXTRACTED FIELDS (JSON):
{fields_json}

RAW DOCUMENT TEXT (use for any detail not in the fields):
{raw_text}

Write the detailed natural language summary now:"""


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

    fields_json = json.dumps(extracted, indent=2, ensure_ascii=False)[:8000]
    raw_snippet = (raw_text or "")[:5000]
    prompt = _PROMPT_TEMPLATE.format(fields_json=fields_json, raw_text=raw_snippet)

    # Prefer the external RunPod generate URL; fall back to the local offline URL.
    # OFFLINE_LLM_GENERATE_URL is often set to localhost (co-located vLLM) which is
    # unreachable when the LLM is running on a remote RunPod pod.
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
                        "max_new_tokens": 2048,
                        "temperature": 0.3,
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
                        "max_tokens": 2048,
                        "temperature": 0.3,
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
