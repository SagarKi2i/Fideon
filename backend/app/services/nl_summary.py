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
You are a senior insurance document analyst. You have been given structured extraction data from an insurance document and the full raw document text. Write a comprehensive, detailed, professional natural language summary covering every piece of information present in the document.

DATA STRUCTURE GUIDE:
The extracted JSON uses a nested schema. Navigate it as follows:
- document_identification: document_type, form_number, edition_date, issuing_organization, line_of_business, total_pages
- parties: named_insured.value, insurer.value, agency.value, broker_producer.value, certificate_holder.value, additional_insureds (array), mortgagee_loss_payee.value
- policy_identifiers: policy_number.value, certificate_number.value, endorsement_number.value, binder_number.value
- dates: effective_date.value, expiration_date.value, issue_date.value, endorsement_effective_date.value
- insured_address: mailing_address.value, city.value, state.value, zip_code.value, risk_location.value
- coverages: array of objects — each has coverage_name, limit, deductible, premium, sublimit
- financial_summary: total_premium.value, taxes_and_fees.value, minimum_earned_premium.value
- vehicles: array — each has year, make, model, vin, usage
- drivers: array — each has name, dob, license_number, state
- properties: array — each has location, construction_type, occupancy, value
- checkboxes: array — each has label, checked (true/false), mark_type
- remarks_and_conditions: array of text blocks
- additional_fields: any other captured fields

PARAGRAPH-BY-PARAGRAPH WRITING PLAN (write each paragraph that has data):
Paragraph 1 — Document Overview: State the document type, form number, edition date, issuing organization, and line of business. State whether it is standalone or part of a policy package and the total number of pages.
Paragraph 2 — Parties: Name the named insured with full address (street, city, state, ZIP). Name the insurer/company. Name the producer/agency/broker with contact details if present. Name any additional insureds.
Paragraph 3 — Policy Identification & Dates: State all policy numbers, certificate numbers, endorsement numbers, and binder numbers present. State the effective and expiration dates, issue date, and any endorsement effective dates.
Paragraph 4 — General Liability Coverage: For each General Liability coverage entry, state the exact coverage name, each-occurrence limit, general aggregate, products-completed operations aggregate, personal and advertising injury limit, damage-to-rented-premises limit, medical expense limit, and deductible. Note if it is occurrence-based or claims-made.
Paragraph 5 — Automobile Coverage: For each auto coverage entry, state the combined single limit or BI/PD split limits and deductibles. List every scheduled vehicle with year, make, model, VIN, and usage. Note coverage triggers (any auto, owned, hired, non-owned).
Paragraph 6 — Workers Compensation & Employers Liability: State the WC statutory limits by state, employers liability each-accident limit, disease-per-employee limit, and disease-policy limit.
Paragraph 7 — Umbrella / Excess Liability: State each occurrence and aggregate limits, the retained limit/SIR, and which underlying policies the umbrella follows.
Paragraph 8 — Other Coverages: Summarise any remaining coverage entries (inland marine, property, professional liability, cyber, crime, etc.) with their limits and deductibles.
Paragraph 9 — Drivers (if present): For each driver, state name, date of birth, license number, and issuing state.
Paragraph 10 — Properties / Locations (if present): For each property, state the address, construction type, occupancy, and insured value.
Paragraph 11 — Financial Summary: State the total premium. State per-coverage premium breakdown if available. State taxes, fees, and minimum earned premium if present.
Paragraph 12 — Checkboxes & Elections: Describe all checked options (e.g. "The form indicates this is a claims-made policy", "Waiver of subrogation applies"). Skip unchecked options unless the label adds meaningful context.
Paragraph 13 — Remarks, Special Conditions & Endorsements: Quote or closely paraphrase the full text of every remarks box, description of operations, special condition, and endorsement narrative. Do not truncate.
Paragraph 14 — Certificate Holder & Additional Insured Provisions: State the certificate holder's full name and address. State whether the certificate holder is also an additional insured. State any cancellation notice provisions (e.g. 30-day written notice). Note any waivers of subrogation.

STRICT STYLE RULES:
- Write in flowing paragraphs — no bullet points, no numbered lists, no headings, no JSON, no markdown
- Use exact dollar figures as written on the form (e.g. "$1,000,000" or "$2,000,000 aggregate")
- Omit any paragraph whose section is completely empty — do not write placeholder text
- Never write "not provided", "N/A", "none", or "not applicable"
- Do NOT copy-paste raw OCR text verbatim — synthesise into professional prose
- Tone: factual, precise, professional — suitable for a claims adjuster, underwriter, or broker
- Minimum length: 6 paragraphs for a full policy document; shorter only for single-page endorsements or binders

EXTRACTED DATA (JSON):
{fields_json}

RAW DOCUMENT TEXT (use for any detail absent from the JSON):
{raw_text}

Write the comprehensive natural language summary now:"""


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

    fields_json = json.dumps(extracted, indent=2, ensure_ascii=False)[:20000]
    raw_snippet = (raw_text or "")[:20000]
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
