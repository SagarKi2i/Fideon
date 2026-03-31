from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date
from typing import Any, Optional

import httpx

from .schemas import (
    AcordAdditionalInterest,
    AcordCarrier,
    ExtractionMeta,
    AcordFormSummary,
    AcordHolder,
    AcordInsured,
    AcordLossHistory,
    AcordOtherNamedInsured,
    AcordPolicyCoverage,
    AcordPolicyInfo,
    AcordPremises,
    AcordPriorCarrier,
    AcordProducer,
)
from . import acord125_fallback as ac125fb
from . import acord25_fallback as ac25fb
from .pdf_acroform import merge_acroform_into_llm_json
from .uir import KeyValue, Table, TextBlock, UnifiedIntermediateRepresentation


logger = logging.getLogger("fideon.acord.pipeline")

# Internal marker on LLM JSON; stripped in build_summary_from_uir → extraction_meta.structured_response_source
ACORD_STRUCTURED_RESPONSE_SOURCE_KEY = "_acord_structured_response_source"


def _url_looks_like_runpod(url: str) -> bool:
    u = (url or "").lower()
    return "runpod" in u or "api.runpod" in u


def _structured_source_label_for_chat_url(url: str) -> str:
    if _url_looks_like_runpod(url):
        return "LLM RunPod response"
    if "api.openai.com" in (url or "").lower():
        return "LLM OpenAI response"
    return "LLM response (OpenAI-compatible endpoint)"


def _structured_source_label_for_offline_generate_url(url: str) -> str:
    if _url_looks_like_runpod(url):
        return "LLM RunPod response"
    return "LLM response (/generate endpoint)"


def _stamp_llm_json_with_response_source(d: dict[str, Any], label: str) -> dict[str, Any]:
    if not d:
        return d
    out = dict(d)
    out[ACORD_STRUCTURED_RESPONSE_SOURCE_KEY] = label
    return out


def _acroform_flat_from_uir(uir: UnifiedIntermediateRepresentation) -> dict[str, str]:
    raw = (uir.layout or {}).get("acroform_fields")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out[str(k)] = s
    return out


def _finalize_llm_json_with_acroform(uir: UnifiedIntermediateRepresentation, result: dict[str, Any]) -> dict[str, Any]:
    if not result:
        return result
    flat = _acroform_flat_from_uir(uir)
    if not flat:
        return result
    return merge_acroform_into_llm_json(result, flat)


def _offline_llm_http_timeout_seconds() -> float:
    """Read timeout for RunPod/vLLM calls (avoid importing app.core.config — circular import with app.routes.acord)."""
    try:
        return float((os.getenv("OFFLINE_LLM_HTTP_TIMEOUT_SECONDS") or "600").strip())
    except ValueError:
        return 600.0


def _acord_offline_generate_url() -> str:
    """RunPod /generate or Ollama-style endpoint (local vLLM, etc.)."""
    url = (os.getenv("OFFLINE_LLM_GENERATE_URL") or os.getenv("RUNPOD_GENERATE_URL") or "").strip()
    if not url:
        return ""
    # Normalize common proxy base URLs so they always point to a `/generate` route.
    # This prevents HTTP 404 when the env var is set without the trailing endpoint.
    url = url.rstrip("/")
    if re.search(r"/generate(\?|$)", url, flags=re.IGNORECASE):
        return url
    # If it's clearly openai-compat (v1/chat/completions), don't rewrite.
    if "chat/completions" in url.lower() or "/v1/" in url.lower():
        return url
    return url + "/generate"


def _acord_use_offline_generate(api_key: str) -> bool:
    """
    When True, ACORD extraction calls OFFLINE_LLM_GENERATE_URL (/generate on RunPod).

    Default: if OFFLINE_LLM_GENERATE_URL is set, use it (ACORD_USE_OFFLINE_LLM defaults to true).
    Set ACORD_USE_OFFLINE_LLM=false to use OpenAI-compatible chat instead when OPENAI_API_KEY is set.

    Previously: offline was skipped whenever OPENAI_API_KEY was non-empty unless
    ACORD_STRICT_LLAMA8B_ONLY — that silently routed ACORD to the wrong endpoint.
    """
    offline_url = _acord_offline_generate_url()
    if not offline_url:
        return False
    prefer_offline = (os.getenv("ACORD_USE_OFFLINE_LLM", "true").strip().lower() in {"1", "true", "yes", "on"})
    if prefer_offline:
        return True
    strict = (os.getenv("ACORD_STRICT_LLAMA8B_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"})
    return strict or not (api_key or "").strip()


# Fallback when OPENAI_MODEL is unset (matches app.core.config.DEFAULT_PRIMARY_LLM_MODEL).
_DEFAULT_OPENAI_COMPAT_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"


def is_vl_model_id(model_name: str) -> bool:
    """True for Qwen2.5-VL (and similar) ids — these need OpenAI-compatible *chat* on vLLM, not /generate."""
    m = (model_name or "").strip().lower()
    if not m:
        return False
    if "-vl-" in m or "qwen2.5-vl" in m or "qwen2_vl" in m or "qwen2-vl" in m:
        return True
    # Some local paths omit explicit "vl" in the folder name but still point to the 72B VL AWQ build.
    if "qwen2.5-72b-instruct-awq" in m or "/qwen2.5-72b-instruct-awq" in m:
        return True
    if "vl-72b" in m or "vl-7b" in m or "vl-32b" in m:
        return True
    return False


def _acord_vl_enabled() -> bool:
    return os.getenv("ACORD_VL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_chat_completions_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.rstrip("/")
    if re.search(r"/v1/chat/completions(\?|$)", u, flags=re.IGNORECASE):
        return u
    # If user provided host root (common in env files), append expected OpenAI path.
    if re.search(r"/v1(\?|$)", u, flags=re.IGNORECASE):
        return u + "/chat/completions"
    return u + "/v1/chat/completions"


def _resolve_acord_chat_completions_url() -> str:
    """Prefer RunPod vLLM OpenAI server; then any OPENAI_CHAT_COMPLETIONS_URL."""
    runpod = _normalize_chat_completions_url((os.getenv("RUNPOD_OPENAI_COMPAT_URL") or "").strip())
    openai_like = _normalize_chat_completions_url((os.getenv("OPENAI_CHAT_COMPLETIONS_URL") or "").strip())
    return runpod or openai_like


def _offline_bearer_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    offline_token = (os.getenv("OFFLINE_LLM_AUTH_TOKEN") or "").strip()
    if offline_token:
        token = offline_token[7:].strip() if offline_token.lower().startswith("bearer ") else offline_token
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _openai_key_bearer_headers(api_key: str) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if (api_key or "").strip():
        headers["Authorization"] = f"Bearer {(api_key or '').strip()}"
    return headers


async def _vl_chat_extract_with_retries(
    *,
    url: str,
    api_key: str,
    model: str,
    hint_line: str,
    schema_hint: dict[str, Any],
    key_values: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    text: str,
    images_b64: list[str],
    max_tokens: int,
    attempts: int,
    acroform_flat: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Qwen2.5-VL via OpenAI-compatible chat (vLLM). Supports optional page images + extraction prompt text.
    """
    use_key = (api_key or "").strip()
    headers = _openai_key_bearer_headers(api_key) if use_key else _offline_bearer_headers()
    correction = ""
    last_content = ""
    for attempt in range(1, attempts + 1):
        prompt = _build_extraction_prompt(
            hint_line=hint_line,
            schema_hint=schema_hint,
            key_values=key_values,
            tables=tables,
            text=text,
            correction=correction,
            acroform_flat=acroform_flat,
        )
        user_parts: list[dict[str, Any]] = []
        if images_b64:
            user_parts.append(
                {
                    "type": "text",
                    "text": (
                        "The following images are rendered pages of the insurance form (page order preserved). "
                        "Cross-check them with the structured text, tables, and key-value hints below.\n\n"
                    ),
                }
            )
            for b64 in images_b64:
                user_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )
        user_parts.append({"type": "text", "text": prompt})

        payload = {
            "model": model,
            "stream": False,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise ACORD insurance form data extraction engine. "
                        "Output must be machine-consumable JSON only."
                    ),
                },
                {"role": "user", "content": user_parts},
            ],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=_offline_llm_http_timeout_seconds()) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.ReadTimeout:
                logger.warning("VL ACORD chat extraction attempt %s/%s timed out", attempt, attempts)
                correction = "Previous request timed out. Return ONLY valid JSON."
                continue

        if resp.status_code >= 400:
            logger.warning(
                "VL ACORD chat extraction failed (attempt %s/%s): %s %s",
                attempt,
                attempts,
                resp.status_code,
                (resp.text or "")[:400],
            )
            correction = f"HTTP {resp.status_code}. Return ONLY valid JSON."
            continue

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        last_content = content or ""
        parsed = _extract_json_candidate(content)
        if not parsed:
            correction = "Output was not valid JSON."
            continue
        if _looks_like_schema_template(parsed):
            correction = "Output looks like schema template placeholders (e.g., string|null), not extracted values."
            continue
        return _postprocess_llm_json(parsed)

    logger.warning(
        "VL ACORD chat extraction returned no valid JSON after %s attempts (first 500 chars): %s",
        attempts,
        last_content[:500],
    )
    return {}


LABELS: dict[str, list[str]] = {
    "producer":                  ["PRODUCER", "AGENCY", "AGENCY NAME"],
    "insured":                   ["INSURED", "NAMED INSURED"],
    "policy_number":             ["POLICY NUMBER", "POLICY NO", "POLICY #", "POLICY NO."],
    "effective_date":            ["EFFECTIVE", "EFF DATE", "EFF", "PROPOSED EFF DATE"],
    "expiration_date":           ["EXPIRATION", "EXP DATE", "EXPIRES", "EXP", "PROPOSED EXP DATE"],
    "certificate_number":        ["CERTIFICATE NUMBER", "CERT NO", "CERT #", "CERTIFICATE NO"],
    "insurer_a":                 ["INSURER A", "INSURER A:", "CARRIER"],
    "insurer_b":                 ["INSURER B", "INSURER B:"],
    "insurer_c":                 ["INSURER C", "INSURER C:"],
    "insurer_d":                 ["INSURER D", "INSURER D:"],
    "naic":                      ["NAIC #", "NAIC NO", "NAIC NUMBER", "NAIC CODE"],
    "holder":                    ["CERTIFICATE HOLDER", "HOLDER"],
    "description_of_operations": ["DESCRIPTION OF OPERATIONS", "DESCRIPTION"],
    "contact_name":              ["CONTACT NAME", "CONTACT"],
    "phone":                     ["PHONE", "PHONE NO", "TELEPHONE", "BUSINESS PHONE"],
    "fax":                       ["FAX", "FAX NO"],
    "email":                     ["E-MAIL ADDRESS", "EMAIL"],
    "cancellation":              ["CANCELLATION", "SHOULD ANY"],
    "each_occurrence":           ["EACH OCCURRENCE", "PER OCCURRENCE"],
    "aggregate":                 ["GENERAL AGGREGATE", "AGGREGATE"],
    "products_ops":              ["PRODUCTS-COMP/OP AGG", "PRODUCTS COMP OPS"],
    "personal_injury":           ["PERSONAL & ADV INJURY"],
    "medical_expense":           ["MED EXP", "MEDICAL EXPENSE"],
    "combined_single_limit":     ["COMBINED SINGLE LIMIT", "CSL"],
    "bodily_injury_person":      ["BODILY INJURY (PER PERSON)"],
    "bodily_injury_accident":    ["BODILY INJURY (PER ACCIDENT)"],
    "property_damage":           ["PROPERTY DAMAGE", "PROP DAMAGE"],
    "employer_liability":        ["E.L. EACH ACCIDENT", "E.L. DISEASE - EA EMPLOYEE", "E.L. DISEASE - POLICY LIMIT"],
    "program_name":              ["COMPANY POLICY OR PROGRAM NAME", "PROGRAM NAME"],
    "underwriter":               ["UNDERWRITER"],
    "agency_customer_id":        ["AGENCY CUSTOMER ID", "CUSTOMER ID"],
    "billing_plan":              ["BILLING PLAN"],
    "payment_plan":              ["PAYMENT PLAN"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).upper()


# ── Engine-based base confidence ─────────────────────────────────────────────
_ENGINE_BASE_CONF: dict[str, float] = {
    "bytescout": 0.90,   # Windows layout extraction with bbox
    "pdfplumber": 0.85,  # Cross-platform layout extraction with bbox + tables
    "pymupdf":   0.82,   # Fast text extraction, good fidelity
    "pypdf2":    0.75,   # Basic text extraction, loses some formatting
    "azure_di":  0.88,   # Azure Document Intelligence layout (cloud OCR + tables)
    "ocr":       0.65,   # OCR — character-recognition errors possible
    "merged":    0.88,   # Staging: combined engines (+ optional Azure DI / bytescout)
    "txt":       0.78,   # Plain-text upload — assumed clean
    "legacy":    0.50,   # Heuristic regex parser — low confidence
}


def _base_conf(uir: "UnifiedIntermediateRepresentation") -> float:
    """Return the base confidence for fields extracted by this UIR's engine."""
    engine = (uir.layout or {}).get("extraction_engine", "pdfplumber")
    return _ENGINE_BASE_CONF.get(str(engine), 0.75)


def _parse_date_any(s: str) -> Optional[date]:
    s = (s or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def build_uir_from_pdf_text(
    *,
    pages_words: list[list[dict[str, Any]]],
    pages_text: list[str],
    pages_tables: list[list[list[list[str]]]],
    extraction_engine: str = "pdfplumber",
) -> UnifiedIntermediateRepresentation:
    uir = UnifiedIntermediateRepresentation(layout={"extraction_engine": extraction_engine})

    for page_idx, text in enumerate(pages_text, start=1):
        if text and text.strip():
            uir.text_blocks.append(TextBlock(text=text, page=page_idx, bbox=None, source="pdf_text"))

    for page_idx, tables in enumerate(pages_tables, start=1):
        for t in tables or []:
            rows = [[(c or "").strip() for c in (row or [])] for row in (t or [])]
            if any(any(cell for cell in row) for row in rows):
                uir.tables.append(Table(page=page_idx, rows=rows))

    for page_idx, words in enumerate(pages_words, start=1):
        if not words:
            continue
        sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))
        lines: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        last_top: float | None = None
        for w in sorted_words:
            top = float(w.get("top", 0))
            if last_top is None or abs(top - last_top) <= 3:
                current.append(w)
            else:
                lines.append(current)
                current = [w]
            last_top = top
        if current:
            lines.append(current)

        for line in lines:
            line_text = " ".join((w.get("text") or "").strip() for w in line if (w.get("text") or "").strip())
            norm_line = _norm(line_text)
            if not norm_line:
                continue
            for field, variants in LABELS.items():
                for lab in variants:
                    if lab not in norm_line:
                        continue
                    lab_words = [w for w in line if _norm(w.get("text") or "") in set(lab.split())]
                    if not lab_words:
                        continue
                    key_x1 = max(float(w.get("x1", 0)) for w in lab_words)
                    key_top = min(float(w.get("top", 0)) for w in lab_words)
                    key_bottom = max(float(w.get("bottom", 0)) for w in lab_words)
                    key_x0 = min(float(w.get("x0", 0)) for w in lab_words)
                    value_words = [w for w in line if float(w.get("x0", 0)) >= key_x1 + 5]
                    value_text = " ".join((w.get("text") or "").strip() for w in value_words if (w.get("text") or "").strip())
                    if not value_text:
                        continue
                    val_x0 = min(float(w.get("x0", 0)) for w in value_words)
                    val_x1 = max(float(w.get("x1", 0)) for w in value_words)
                    val_top = min(float(w.get("top", 0)) for w in value_words)
                    val_bottom = max(float(w.get("bottom", 0)) for w in value_words)
                    uir.key_values.append(
                        KeyValue(
                            key=lab, value=value_text, page=page_idx,
                            key_bbox=[key_x0, key_top, key_x1, key_bottom],
                            value_bbox=[val_x0, val_top, val_x1, val_bottom],
                            confidence=0.85,
                        )
                    )
                    break

    return uir


# ── Full schema hint sent to the LLM ─────────────────────────────────────────
_SCHEMA_HINT: dict[str, Any] = {
    "form_type": "string|null",
    "form_version": "string|null",
    "certificate_number": "string|null",
    "revision_date": "string|null",
    "date": "string|null  # top-level form date",
    "producer": {
        "name": "string|null",
        "contact_name": "string|null",
        "address": "string|null",
        "city": "string|null",
        "state": "string|null",
        "postal_code": "string|null",
        "phone": "string|null",
        "fax": "string|null",
        "email": "string|null",
        "agency_customer_id": "string|null",
        "subcode": "string|null",
        "producer_license_no": "string|null",
        "national_producer_number": "string|null",
    },
    "insured": {
        "name": "string|null  # first named insured",
        "contact_name": "string|null",
        "mailing_address": "string|null",
        "city": "string|null",
        "state": "string|null",
        "postal_code": "string|null",
        "phone": "string|null",
        "fax": "string|null",
        "email": "string|null",
        "website": "string|null",
        "entity_type": "string|null  # Corporation/LLC/Partnership/etc.",
        "gl_code": "string|null",
        "sic": "string|null",
        "naics": "string|null",
        "fein": "string|null",
    },
    "other_named_insureds": [
        {
            "name": "string|null",
            "mailing_address": "string|null",
            "city": "string|null",
            "state": "string|null",
            "postal_code": "string|null",
            "phone": "string|null",
            "website": "string|null",
            "entity_type": "string|null",
            "gl_code": "string|null",
            "sic": "string|null",
            "naics": "string|null",
            "fein": "string|null",
        }
    ],
    "holder": {
        "name": "string|null",
        "address": "string|null",
        "city": "string|null",
        "state": "string|null",
        "postal_code": "string|null",
        "is_additional_insured": "boolean|null",
        "is_subrogation_waived": "boolean|null",
    },
    "policy_info": {
        "carrier": {"name": "string|null", "naic_number": "string|null"},
        "program_name": "string|null",
        "program_code": "string|null",
        "policy_number": "string|null",
        "proposed_eff_date": "string|null  # MM/DD/YYYY",
        "proposed_exp_date": "string|null  # MM/DD/YYYY",
        "billing_plan": "string|null  # Direct/Agency",
        "payment_plan": "string|null  # Annual/Monthly/etc.",
        "method_of_payment": "string|null  # Cash/EFT/etc.",
        "deposit": "string|null",
        "minimum_premium": "string|null",
        "policy_premium": "string|null",
        "transaction_type": "string|null  # Quote/Issue Policy/Renew/Change/Cancel",
        "transaction_date": "string|null",
        "underwriter": "string|null",
        "underwriter_office": "string|null",
    },
    "lines_of_business_indicated": [
        "list of strings — every line of business that is checked/marked/selected on the form, e.g. 'BUSINESS OWNERS', 'TRUCKERS', 'COMMERCIAL GENERAL LIABILITY'"
    ],
    "coverages": [
        {
            "line_of_business": "GL|AUTO|WC|UMB|PROPERTY|CRIME|BOP|TRUCKERS|null",
            "policy_number": "string|null",
            "effective_date": "YYYY-MM-DD|null",
            "expiration_date": "YYYY-MM-DD|null",
            "claims_made": "boolean|null",
            "occurrence_type": "boolean|null",
            "additional_insured": "boolean|null",
            "waiver_of_subrogation": "boolean|null",
            "each_occurrence": "string|null",
            "damage_to_rented_premises": "string|null",
            "medical_expense": "string|null",
            "personal_advertising_injury": "string|null",
            "general_aggregate": "string|null",
            "products_comp_ops_aggregate": "string|null",
            "combined_single_limit": "string|null",
            "bodily_injury_per_person": "string|null",
            "bodily_injury_per_accident": "string|null",
            "property_damage": "string|null",
            "occurrence_limit": "string|null",
            "aggregate_limit": "string|null",
            "deductible": "string|null",
            "retention": "string|null",
            "retroactive_date": "string|null",
            "wc_statutory_limits": "boolean|null",
            "employer_liability_each_accident": "string|null",
            "employer_liability_each_employee": "string|null",
            "employer_liability_policy_limit": "string|null",
            "insurers": [{"name": "string|null", "naic_number": "string|null"}],
        }
    ],
    "premises": [
        {
            "location_number": "string|null",
            "street": "string|null",
            "city": "string|null",
            "state": "string|null",
            "county": "string|null",
            "zip": "string|null",
            "interest": "string|null",
            "full_time_employees": "string|null",
            "part_time_employees": "string|null",
            "annual_revenues": "string|null",
            "total_building_area_sqft": "string|null",
            "description_of_operations": "string|null",
            "area_leased_to_others": "string|null",
        }
    ],
    "prior_carriers": [
        {
            "year": "string|null",
            "category": "string|null  # General Liability/Automobile/Property/Other",
            "carrier": "string|null",
            "policy_number": "string|null",
            "premium": "string|null",
            "effective_date": "string|null",
            "expiration_date": "string|null",
        }
    ],
    "loss_history": [
        {
            "date_of_occurrence": "string|null",
            "line_type": "string|null",
            "description": "string|null",
            "date_of_claim": "string|null",
            "amount_paid": "string|null",
            "amount_reserved": "string|null",
            "subrogation": "boolean|null",
            "claim_open": "boolean|null",
        }
    ],
    "additional_interests": [
        {
            "interest_type": "string|null",
            "name": "string|null",
            "address": "string|null",
            "location": "string|null",
            "building": "string|null",
            "loan_reference": "string|null",
        }
    ],
    "description_of_operations": "string|null",
    "nature_of_business": "string|null",
    "cancellation_notice_days": "integer|null",
    "additional_remarks": "string|null",
    "extra_fields": {
        "any_key": "any additional fields present in the document that do not fit above"
    },
    "extraction_meta": {
        "form_type_detected": "string|null",
        "blank_in_document": [
            "list of field paths that are labeled sections on the form but have no filled-in data, e.g. ['description_of_operations', 'premises[0].street']"
        ],
        "not_applicable_to_form_type": [
            "list of field paths that do not exist on this ACORD form type at all, e.g. ['holder', 'cancellation_notice_days'] for ACORD 125"
        ],
        "all_checked_items": [
            "every item marked with X or x anywhere in the document"
        ],
        "remarks": [
            "notes about ambiguous values, OCR uncertainty, or low-confidence extractions"
        ],
    },
}


def _is_small_extraction_model(model_name: str) -> bool:
    """True for 8B-class extractors (compact schema + multi-pass)."""
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


def _repair_truncated_json_object(fragment: str) -> Optional[dict[str, Any]]:
    """
    When the LLM hits max_new_tokens mid-stream, JSON often ends inside a string
    (e.g. `"email": "certificates@westfie`). Close the open string and any open
    `{` / `[` so json.loads can recover a partial but usable object.
    """
    s = (fragment or "").strip()
    if "{" not in s:
        return None
    start = s.find("{")
    s = s[start:]

    stack: list[str] = []  # "{" or "["
    in_string = False
    escape = False
    for ch in s:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        # not in string
        if ch == '"':
            in_string = True
        elif ch == "{":
            stack.append("{")
        elif ch == "[":
            stack.append("[")
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    fix = s.rstrip()
    # Trailing `:` without value — common when cut right after a key
    if fix.endswith(":"):
        fix += " null"
    else:
        fix = re.sub(r",\s*$", "", fix)
    if in_string:
        fix += '"'
    while stack:
        top = stack.pop()
        fix += "}" if top == "{" else "]"

    try:
        parsed = json.loads(fix)
        if isinstance(parsed, dict):
            logger.warning(
                "Recovered truncated JSON (%d → %d chars) — raise ACORD_EXTRACT_MAX_NEW_TOKENS or retries",
                len(s),
                len(fix),
            )
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def _extract_json_candidate(raw: str) -> Optional[dict[str, Any]]:
    """
    Extract the first valid JSON object from model output.

    Handles:
    - Markdown fences (```json … ```)
    - Preamble text before the opening brace
    - Postamble text after the closing brace
    - Multiple candidate JSON spans (returns the first parseable dict)
    - Truncated JSON when generation stopped mid-object (offline max_new_tokens)
    """
    content = (raw or "").strip()
    if not content:
        return None

    # Strip markdown fences.
    content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
    content = re.sub(r"\s*```\s*$", "", content)
    content = content.strip()

    # Try the whole string first (fastest and safest for clean output).
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Walk every `{` in the string and try to find a valid JSON object starting there.
    # This handles preamble text like "Sure, here is the JSON:\n{..." or
    # postamble like "}. Let me know if you need anything else."
    for start in range(len(content)):
        if content[start] != "{":
            continue
        # Search for matching closing `}` from the end backwards for efficiency.
        for end in range(len(content), start, -1):
            if content[end - 1] != "}":
                continue
            candidate = content[start:end]
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

    # Truncated stream: no closing `}` or string not closed — repair and parse.
    repaired = _repair_truncated_json_object(content)
    if repaired is not None:
        return repaired
    return None


def _looks_like_schema_template(payload: dict[str, Any]) -> bool:
    placeholder_re = re.compile(r"(string\|null|number\|null|boolean\|null|array\||object\|)", flags=re.IGNORECASE)
    placeholder_hits = 0
    scalar_total = 0

    def _walk(v: Any) -> None:
        nonlocal placeholder_hits, scalar_total
        if isinstance(v, dict):
            for vv in v.values():
                _walk(vv)
            return
        if isinstance(v, list):
            for vv in v:
                _walk(vv)
            return
        if isinstance(v, str):
            scalar_total += 1
            if placeholder_re.search(v):
                placeholder_hits += 1

    _walk(payload)
    return scalar_total >= 5 and placeholder_hits >= max(3, scalar_total // 3)


def _small_model_schema_hint() -> dict[str, Any]:
    # Compact hint for small-context models; still preserves required structure.
    return {
        "form_type": "string|null",
        "producer": {"name": "string|null", "phone": "string|null", "email": "string|null", "agency_customer_id": "string|null"},
        "insured": {"name": "string|null", "mailing_address": "string|null", "phone": "string|null", "entity_type": "string|null", "fein": "string|null"},
        "other_named_insureds": [{"name": "string|null", "mailing_address": "string|null"}],
        "policy_info": {
            "carrier": {"name": "string|null", "naic": "string|null"},
            "policy_number": "string|null",
            "proposed_eff_date": "string|null",
            "proposed_exp_date": "string|null",
            "billing_plan": "string|null",
            "payment_plan": "string|null",
            "deposit": "string|null",
            "minimum_premium": "string|null",
            "policy_premium": "string|null",
        },
        "coverages": [{"line_type": "string|null", "policy_number": "string|null", "effective_date": "string|null", "expiration_date": "string|null"}],
        "premises": [{"loc_no": "string|null", "street": "string|null", "city": "string|null", "state": "string|null"}],
        "prior_carriers": [{"line_type": "string|null", "carrier": "string|null", "policy_number": "string|null"}],
        "lines_of_business_indicated": ["string"],
        "loss_history": [{"line_type": "string|null", "description": "string|null"}],
        "extraction_meta": {
            "form_type_detected": "string|null",
            "blank_in_document": ["string"],
            "not_applicable_to_form_type": ["string"],
            "all_checked_items": ["string"],
            "remarks": ["string"],
        },
        "extra_fields": {},
    }


def _extract_text_from_generate_response(data: dict[str, Any]) -> str:
    for key in ("response", "generated_text", "text", "output"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        text = first.get("text") if isinstance(first, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


async def _offline_extract_with_retries(
    *,
    model: str,
    prompt_builder: Any,
    attempts: int,
    max_tokens: int,
) -> dict[str, Any]:
    offline_url = _acord_offline_generate_url()
    if not offline_url:
        return {}
    offline_token = (os.getenv("OFFLINE_LLM_AUTH_TOKEN") or "").strip()
    headers = {"Content-Type": "application/json"}
    if offline_token:
        token = offline_token[7:].strip() if offline_token.lower().startswith("bearer ") else offline_token
        headers["Authorization"] = f"Bearer {token}"

    correction = ""
    last_content = ""
    # Delays between retries (seconds).
    # Normal retries use short delays; cold-start (524) gets a long delay so the
    # model has time to finish loading (~103s on RTX 3090) before we retry.
    _RETRY_DELAYS = [0, 5, 15, 30]
    _COLD_START_DELAY = 110  # seconds to wait after a 524 (Cloudflare timeout = model loading)
    async with httpx.AsyncClient(timeout=_offline_llm_http_timeout_seconds()) as client:
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                delay = _RETRY_DELAYS[min(attempt - 2, len(_RETRY_DELAYS) - 1)]
                if delay:
                    await asyncio.sleep(delay)
            prompt = prompt_builder(correction)
            try:
                resp = await client.post(
                    offline_url,
                    headers=headers,
                    json={
                        "prompt": prompt,
                        "model": model,
                        "max_new_tokens": max_tokens,
                        "temperature": 0.0,
                        "raw": True,
                    },
                )
            except httpx.ReadTimeout:
                logger.warning("offline ACORD extraction attempt %s/%s timed out", attempt, attempts)
                correction = "Previous request timed out. Return ONLY valid JSON."
                continue
            if resp.status_code == 524:
                # Cloudflare "A Timeout Occurred" — RunPod model is cold-loading (~103s).
                # Wait long enough for the model to finish before retrying.
                logger.info(
                    "offline ACORD extraction attempt %s/%s: RunPod cold-start timeout (524); "
                    "waiting %ss for model to finish loading …",
                    attempt, attempts, _COLD_START_DELAY,
                )
                await asyncio.sleep(_COLD_START_DELAY)
                correction = ""
                continue
            if resp.status_code in (502, 503, 504):
                # Model still loading or gateway not ready — wait and retry without spending correction budget.
                logger.info(
                    "offline ACORD extraction attempt %s/%s: server not ready (%s), will retry",
                    attempt, attempts, resp.status_code,
                )
                correction = ""
                continue
            if resp.status_code >= 400:
                logger.warning(
                    "offline ACORD extraction attempt %s/%s: url=%s returned HTTP %s — response body: %s",
                    attempt,
                    attempts,
                    offline_url,
                    resp.status_code,
                    resp.text[:300],
                )
                correction = f"HTTP {resp.status_code}. Return ONLY valid JSON."
                continue

            content_type = (resp.headers.get("content-type") or "").lower()
            if "application/json" in content_type:
                text = _extract_text_from_generate_response(resp.json())
            else:
                text = (resp.text or "").strip()
            last_content = text
            parsed = _extract_json_candidate(text)
            if not parsed:
                correction = "Output was not valid JSON."
                continue
            if _looks_like_schema_template(parsed):
                correction = "Output looks like schema template placeholders (e.g., string|null), not extracted values."
                continue
            return _postprocess_llm_json(parsed)

    logger.warning("offline ACORD extraction failed after %s attempts (first 500 chars): %s", attempts, last_content[:500])
    return {}


def _merge_extraction_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """
    Merge partial extraction objects from multiple passes.
    - Keep existing non-empty scalar values.
    - Merge nested dicts recursively.
    - Union lists (de-duplicate by normalized JSON string form).
    """
    out = dict(base)
    for k, v in (incoming or {}).items():
        if k not in out:
            out[k] = v
            continue

        cur = out.get(k)
        if isinstance(cur, dict) and isinstance(v, dict):
            out[k] = _merge_extraction_dicts(cur, v)
            continue
        if isinstance(cur, list) and isinstance(v, list):
            seen: set[str] = set()
            merged: list[Any] = []
            for item in (cur + v):
                sig = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
                if sig in seen:
                    continue
                seen.add(sig)
                merged.append(item)
            out[k] = merged
            continue
        # Prefer current non-empty scalar; otherwise take incoming.
        if cur in (None, "", [], {}):
            out[k] = v
    return out


def _regex_pre_extract(text: str) -> dict[str, list[str]]:
    """
    Pull well-structured values from raw text using regex BEFORE sending to LLM.
    These are injected as high-confidence hints so the LLM doesn't have to guess.
    """
    # Dates: MM/DD/YYYY
    dates = sorted(set(re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)))

    # Dollar amounts: $1,000,000 or 1,000,000 (min 6 digits to avoid noise)
    amounts = sorted(set(re.findall(r"\$[\d,]{6,}", text)))

    # Policy numbers: alphanumeric tokens with hyphens that look like policy IDs
    # (≥6 chars, contains at least one letter and one digit, may have hyphens/spaces)
    raw_policy = re.findall(r"\b([A-Z]{1,5}[-\s]?\d[\d\-]{4,20})\b", text)
    policy_numbers = sorted({p.strip() for p in raw_policy if len(p) >= 6})

    # NAIC codes: 5-digit standalone numbers
    naic_codes = sorted(set(re.findall(r"\bNAIC[:\s#]+(\d{5})\b", text, re.IGNORECASE)))
    if not naic_codes:
        # Fallback: any 5-digit number near the word NAIC
        naic_codes = sorted(set(re.findall(r"\b(\d{5})\b", text)))[:10]

    # Certificate numbers
    cert_numbers = sorted(set(re.findall(
        r"\b(?:CERT(?:IFICATE)?[\s#NO.:]+)([A-Z0-9\-]{4,20})\b", text, re.IGNORECASE
    )))

    out: dict[str, Any] = {
        "dates_found": dates[:20],
        "dollar_amounts_found": amounts[:20],
        "policy_numbers_found": policy_numbers[:10],
        "naic_codes_found": naic_codes[:10],
        "certificate_numbers_found": cert_numbers[:5],
    }
    if _is_probable_acord25_context(text):
        out["acord25_anchor_hints"] = _regex_acord25_boost(text)
    return out


def _is_probable_acord25_context(text: str) -> bool:
    u = (text or "").upper()
    return "ACORD 25" in u or "CERTIFICATE OF LIABILITY INSURANCE" in u or (
        "CERTIFICATE" in u and "HOLDER" in u and "INSURED" in u
    )


def _looks_like_us_city_state_zip_line(s: str) -> bool:
    """
    True if the string is a single US mailing line 'City, ST 12345' (or ZIP+4).
    These are often mis-read as named insured / producer when the real name is on another line.
    """
    t = (s or "").strip()
    if len(t) < 8 or len(t) > 130:
        return False
    # One comma before state: Naperville, IL  60563
    return bool(
        re.match(r"^[^,\n]{1,90},\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*$", t, flags=re.IGNORECASE)
    )


def _lines_after_anchor_until(
    text: str,
    anchor_pattern: str,
    stop_pattern: str,
    *,
    max_lines: int = 8,
) -> list[str]:
    """Lines after first line matching `anchor_pattern`, until `stop_pattern` matches a line start."""
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    anchor_rx = re.compile(anchor_pattern, re.IGNORECASE)
    stop_rx = re.compile(stop_pattern, re.IGNORECASE)
    started = False
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not started:
            if anchor_rx.search(s):
                started = True
            continue
        if not s:
            if out:
                break
            continue
        if stop_rx.match(s):
            break
        out.append(s)
        if len(out) >= max_lines:
            break
    return out


def _pick_acord25_entity_name(candidates: list[str]) -> Optional[str]:
    """First line that looks like a company / person name, not an address-only row."""
    for raw in candidates:
        c = raw.strip()
        if len(c) < 4 or len(c) > 180:
            continue
        if _is_suspicious_name(c):
            continue
        # Street address: leading number + street word
        if re.match(r"^\d{1,6}\s+[A-Za-z0-9#.\-]+\s+(ST|AVE|RD|BLVD|DR|LN|WAY|CT|HWY)\b", c, re.I):
            continue
        if re.search(r"\b(LLC|INC\.?|CORP|LTD|L\.L\.C|LP|LLP|COMPANY|CO\.)\b", c, re.I):
            return c
        if len(c) >= 10:
            return c
    return None


def _regex_acord25_boost(text: str) -> dict[str, Any]:
    """
    Deterministic hints for ACORD 25 layout: lines following PRODUCER / INSURED anchors.
    Complements the LLM when table text is noisy or merged across engines.
    """
    hints: dict[str, Any] = {}
    prod_lines = _lines_after_anchor_until(
        text,
        r"^\s*PRODUCER\b",
        r"^\s*(NAMED\s+INSURED|INSURED)\b",
    )
    if not prod_lines:
        prod_lines = _lines_after_anchor_until(
            text,
            r"PRODUCER\s+INFORMATION",
            r"^\s*(NAMED\s+INSURED|INSURED)\b",
        )
    pn = _pick_acord25_entity_name(prod_lines)
    if pn:
        hints["producer_name_hint"] = pn

    ins_lines = _lines_after_anchor_until(
        text,
        r"^\s*NAMED\s+INSURED\b",
        r"^\s*(COVERAGE|TYPE\s+OF\s+INSURANCE|CERTIFICATE\s+HOLDER)\b",
    )
    if not ins_lines:
        ins_lines = _lines_after_anchor_until(
            text,
            r"^\s*INSURED\b",
            r"^\s*(COVERAGE|TYPE\s+OF\s+INSURANCE|CERTIFICATE\s+HOLDER|PRODUCER)\b",
        )
    inn = _pick_acord25_entity_name(ins_lines)
    if inn:
        hints["insured_name_hint"] = inn

    emails = sorted(set(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)))
    if emails:
        hints["emails_found"] = emails[:6]
    phones = sorted(set(re.findall(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b", text)))
    if phones:
        hints["phones_found"] = phones[:6]

    return hints


# Confidence when producer/insured name comes only from ACORD 25 anchor regex (not LLM/KV).
REGEX_NAME_FALLBACK_CONF = 0.72
# Two-column PRODUCER/INSURED line + deterministic block parsing (stronger than anchor regex).
ACORD25_DETERMINISTIC_NAME_CONF = 0.94


def _apply_acord25_regex_name_fallback(
    raw_text: str,
    form_type: Optional[str],
    prod_name: Optional[str],
    ins_name: Optional[str],
) -> tuple[Optional[str], Optional[str], bool, bool]:
    """If LLM left names empty, fill from anchor hints when they pass sanity checks."""
    ft = (form_type or "") + " " + (raw_text[:600] or "")
    if "25" not in ft and not _is_probable_acord25_context(raw_text):
        return prod_name, ins_name, False, False
    boost = _regex_acord25_boost(raw_text)
    pn_hint = boost.get("producer_name_hint")
    in_hint = boost.get("insured_name_hint")
    p_boost = False
    i_boost = False
    if (not prod_name or _is_suspicious_name(prod_name)) and pn_hint and not _is_suspicious_name(pn_hint):
        prod_name = pn_hint.strip()
        p_boost = True
    if (not ins_name or _is_suspicious_name(ins_name)) and in_hint and not _is_suspicious_name(in_hint):
        ins_name = in_hint.strip()
        i_boost = True
    return prod_name, ins_name, p_boost, i_boost


def _build_extraction_prompt(
    *,
    hint_line: str,
    schema_hint: dict[str, Any],
    key_values: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    text: str,
    correction: str = "",
    acroform_flat: dict[str, str] | None = None,
) -> str:
    acro_block = ""
    if acroform_flat:
        acro_block = (
            "\n═══════════════════════════════════════════════════════\n"
            "AUTHORITATIVE PDF FORM FIELDS (AcroForm — use verbatim; do not contradict)\n"
            "═══════════════════════════════════════════════════════\n"
            "These values come from embedded PDF form widgets (fillable fields). "
            "Map them into TARGET SCHEMA; they override noisy OCR/layout text when they conflict.\n\n"
            f"{json.dumps(acroform_flat, indent=2, ensure_ascii=False)}\n\n"
        )
    prompt = f"""{hint_line}{acro_block}You are an expert data extraction engine for ACORD insurance forms.

═══════════════════════════════════════════════════════
MANDATORY EXTRACTION RULES
═══════════════════════════════════════════════════════
1. Return ONLY valid JSON — no markdown fences, no commentary, no trailing text.
2. Extract EVERY value that is actually present. DO NOT leave a field null if the value exists anywhere in the text.
3. If a field is genuinely absent or blank, use null — never fabricate values.
4. Put any field not in the schema into "extra_fields".

═══════════════════════════════════════════════════════
CHECKBOX / MARKED-ITEM DETECTION
═══════════════════════════════════════════════════════
- An "x" or "X" immediately before an item name means that item is SELECTED.
- Scan ALL sections: INDICATE LINES OF BUSINESS table, ATTACHMENTS list, transaction type row, billing plan row, entity type row, etc.
- "lines_of_business_indicated" must include EVERY item with an x/X in BOTH the LINES OF BUSINESS table AND the ATTACHMENTS section.
  Example: "x BUSINESS OWNERS", "x TRUCKERS", "x CONTRACTORS SUPPLEMENT" → all three go in lines_of_business_indicated.
- "transaction_type": look for "X | quote", "X | ISSUE POLICY", "X | RENEW", "X | CHANGE", "X | CANCEL", "X | BOUND".
  The word immediately after the X marker (ignoring "|") is the selected transaction type.
  "X | quote" → transaction_type = "QUOTE". "X | ISSUE POLICY" → "ISSUE POLICY". Do NOT pick the unselected ones.
- "billing_plan" for policy_info: look for "|_| DIRECT | XX | AGENCY" or similar — whichever side has the X mark is selected.
  "XX | AGENCY" → billing_plan = "AGENCY". "|_| DIRECT" → DIRECT is NOT selected.

═══════════════════════════════════════════════════════
ACORD 125 PREMIUM COLUMN ORDER (CRITICAL — DO NOT SWAP)
═══════════════════════════════════════════════════════
The policy information row columns are in this EXACT left-to-right order:
  PROPOSED EFF DATE | PROPOSED EXP DATE | BILLING PLAN | PAYMENT PLAN | METHOD OF PAYMENT | DEPOSIT | MINIMUM PREMIUM | POLICY PREMIUM
Example row: "07/02/2025  07/01/2026  Annual  Cash  $ 12000  $ 4500  $ 6000"
  → proposed_eff_date = "07/02/2025"
  → proposed_exp_date = "07/01/2026"
  → payment_plan = "Annual"
  → method_of_payment = "Cash"
  → deposit = "$ 12000"
  → minimum_premium = "$ 4500"
  → policy_premium = "$ 6000"

═══════════════════════════════════════════════════════
FORM-TYPE SPECIFIC RULES
═══════════════════════════════════════════════════════
- ACORD 125 (Commercial Insurance Application):
    • Has NO certificate holder section → set holder = null, add "holder" to extraction_meta.not_applicable_to_form_type
    • Has NO cancellation_notice_days → add to not_applicable_to_form_type
    • All policy/carrier/program/underwriter data belongs in policy_info
    • Multiple named insured blocks on page 1 → each goes in other_named_insureds[]
    • Premises section rows (LOC #, BLD #) → each non-empty location goes in premises[]
    • Prior Carrier Information tables → each filled row goes in prior_carriers[]
- ACORD 25 (Certificate of Insurance):
    • Has certificate holder, cancellation_notice_days, coverage blocks with limits
    • Has NO policy_info, other_named_insureds, premises, prior_carriers
    • INSURED name and address are in the top-left box labeled "INSURED" — extract the
      COMPANY NAME as insured.name (first non-blank line), address lines into insured.mailing_address,
      city/state/zip into insured.city / insured.state / insured.postal_code.
    • PRODUCER (agency) is in the top-left corner above the insured block — extract
      agency name as producer.name, address, phone/fax into producer.phone / producer.fax.
    • INSURERS A–E are listed on the right side: each line has insurer letter + name + NAIC #.
      Extract into coverages[].insurers[] with {{name, naic_number, insurer_letter}}.
    • CERTIFICATE HOLDER block (bottom-left) → holder.name + holder.address.
    • COVERAGE TABLE column order (left → right):
        TYPE OF INSURANCE | ADDL INSR | SUBR WVD | POLICY NUMBER | POLICY EFF | POLICY EXP | LIMITS
      Extract policy_number, effective_date, expiration_date from the correct columns.
    • For COMMERCIAL GENERAL LIABILITY the LIMITS sub-rows (top → bottom) are:
        EACH OCCURRENCE            → coverages[i].limits.each_occurrence
        DAMAGE TO RENTED PREMISES  → coverages[i].limits.damage_to_rented_premises
        MED EXP (Any one person)   → coverages[i].limits.med_exp
        PERSONAL & ADV INJURY      → coverages[i].limits.personal_adv_injury
        GENERAL AGGREGATE          → coverages[i].limits.general_aggregate
        PRODUCTS - COMP/OP AGG     → coverages[i].limits.products_comp_op_agg
    • For AUTOMOBILE LIABILITY the LIMITS sub-rows are:
        COMBINED SINGLE LIMIT      → coverages[i].limits.combined_single_limit
        BODILY INJURY (Per person) → coverages[i].limits.bodily_injury_per_person
        BODILY INJURY (Per acc.)   → coverages[i].limits.bodily_injury_per_accident
        PROPERTY DAMAGE (Per acc.) → coverages[i].limits.property_damage_per_accident
    • For UMBRELLA / EXCESS LIABILITY:
        EACH OCCURRENCE            → coverages[i].limits.each_occurrence
        AGGREGATE                  → coverages[i].limits.aggregate
    • For WORKERS COMPENSATION AND EMPLOYERS LIABILITY:
        E.L. EACH ACCIDENT         → coverages[i].limits.el_each_accident
        E.L. DISEASE - EA EMPLOYEE → coverages[i].limits.el_disease_ea_employee
        E.L. DISEASE - POLICY LIMIT→ coverages[i].limits.el_disease_policy_limit
    • Dollar amounts look like "$1,000,000" — include the "$" and commas exactly as printed.
    • coverage_type should be one of: "COMMERCIAL GENERAL LIABILITY", "AUTOMOBILE LIABILITY",
      "UMBRELLA LIABILITY", "EXCESS LIABILITY", "WORKERS COMPENSATION", "OTHER".
    • CRITICAL (ACORD 25): When the form is ACORD 25, fill producer.name and insured.name from the
      first substantive company/agency line under the PRODUCER and NAMED INSURED / INSURED headings in the text.
      Do not leave them null if those headings and a company name appear anywhere in FULL DOCUMENT TEXT.
      Never use footer/legend sentences (e.g. about ADDITIONAL INSURED provisions, SUBROGATION, CERTIFICATE HOLDER)
      as producer or insured names — those are not names.
    • CRITICAL (tables): The word LIMITS is a column header — never use it as policy_number.
      Policy numbers contain digits and look like real policy IDs, not single English words.
- For sections that exist as labeled headers but are completely blank/unfilled:
    → add those field paths to extraction_meta.blank_in_document (do NOT fabricate data)

═══════════════════════════════════════════════════════
extraction_meta REQUIREMENTS
═══════════════════════════════════════════════════════
Always populate extraction_meta with:
- form_type_detected: the ACORD form number you detected
- blank_in_document: field paths of sections present on the form but left blank (e.g. "description_of_operations", "premises", "prior_carriers", "producer.producer_license_no")
- not_applicable_to_form_type: field paths that simply don't exist on this form type
- all_checked_items: every X-marked item found anywhere in the document
- remarks: any ambiguous values, OCR noise corrections, or low-confidence notes

TARGET SCHEMA:
{json.dumps(schema_hint, indent=2)}

REGEX PRE-EXTRACTED VALUES (high confidence — use these to fill fields, do not ignore).
For ACORD 25, acord25_anchor_hints.producer_name_hint / insured_name_hint are derived from heading anchors:
{json.dumps(_regex_pre_extract(text), indent=2)}

KEY_VALUES (from layout scanner — high accuracy):
{json.dumps(key_values)}

TABLES (from PDF table extraction):
{json.dumps(tables)}

FULL DOCUMENT TEXT:
{text}
"""
    if correction:
        prompt += (
            "\n\nPREVIOUS_OUTPUT_ISSUE:\n"
            f"{correction}\n"
            "Return ONLY valid JSON object matching TARGET SCHEMA. "
            "Do not include markdown fences."
        )
    extra = (os.getenv("ACORD_EXTRACTION_PROMPT_SUFFIX") or "").strip()
    if extra:
        prompt += (
            "\n\n═══════════════════════════════════════════════════════\n"
            "EXTRA INSTRUCTIONS (from ACORD_EXTRACTION_PROMPT_SUFFIX)\n"
            "═══════════════════════════════════════════════════════\n"
            f"{extra}\n"
        )
    return prompt


async def _extract_with_retries(
    *,
    url: str,
    api_key: str,
    model: str,
    hint_line: str,
    schema_hint: dict[str, Any],
    key_values: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    text: str,
    max_tokens: int,
    attempts: int,
    acroform_flat: dict[str, str] | None = None,
) -> dict[str, Any]:
    api_key_stripped = (api_key or "").strip()
    use_offline = _acord_use_offline_generate(api_key_stripped)
    if use_offline:
        offline_model = (os.getenv("OFFLINE_LLM_MODEL_NAME") or "").strip() or model
        offline_res = await _offline_extract_with_retries(
            model=offline_model,
            prompt_builder=lambda correction: _build_extraction_prompt(
                hint_line=hint_line,
                schema_hint=schema_hint,
                key_values=key_values,
                tables=tables,
                text=text,
                correction=correction,
                acroform_flat=acroform_flat,
            ),
            attempts=attempts,
            max_tokens=max_tokens,
        )
        # If offline generation fails (e.g., 404 endpoint or invalid JSON), fall back
        # to the OpenAI-compatible path when configured, so we don't silently degrade.
        if offline_res:
            return offline_res
        logger.warning("offline extraction returned empty; falling back to openai-compatible extraction")

    if not api_key_stripped:
        return {}

    correction = ""
    last_content = ""
    for attempt in range(1, attempts + 1):
        prompt = _build_extraction_prompt(
            hint_line=hint_line,
            schema_hint=schema_hint,
            key_values=key_values,
            tables=tables,
            text=text,
            correction=correction,
            acroform_flat=acroform_flat,
        )
        payload = {
            "model": model,
            "stream": False,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise ACORD insurance form data extraction engine. "
                        "Output must be machine-consumable JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }

        headers = {"Content-Type": "application/json"}
        if api_key_stripped:
            headers["Authorization"] = f"Bearer {api_key_stripped}"
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                url,
                headers=headers,
                json=payload,
            )
        if resp.status_code >= 400:
            logger.warning(
                "OpenAI-compatible extraction failed (attempt %s/%s): %s %s",
                attempt,
                attempts,
                resp.status_code,
                (resp.text or "")[:300],
            )
            return {}

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        last_content = content or ""
        parsed = _extract_json_candidate(content)
        if not parsed:
            correction = "Output was not valid JSON."
            continue
        if _looks_like_schema_template(parsed):
            correction = "Output looks like schema template placeholders (e.g., string|null), not extracted values."
            continue
        return parsed

    logger.warning(
        "Extraction LLM returned non-JSON/content-template after %s attempts (first 500 chars): %s",
        attempts,
        last_content[:500],
    )
    return {}


async def openai_compat_extract_structured(
    uir: UnifiedIntermediateRepresentation,
    form_type_hint: Optional[str] = None,
) -> dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    url = _resolve_acord_chat_completions_url() or "https://api.openai.com/v1/chat/completions"
    model = (os.getenv("OPENAI_MODEL") or _DEFAULT_OPENAI_COMPAT_MODEL).strip()
    strict_llama8b_only = (os.getenv("ACORD_STRICT_LLAMA8B_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"})
    offline_url = _acord_offline_generate_url()
    use_offline = _acord_use_offline_generate(api_key)
    if strict_llama8b_only and not offline_url:
        logger.warning(
            "ACORD_STRICT_LLAMA8B_ONLY is enabled but no offline URL is set "
            "(OFFLINE_LLM_GENERATE_URL or RUNPOD_GENERATE_URL)."
        )
        return {}

    offline_model_name = (os.getenv("OFFLINE_LLM_MODEL_NAME") or "").strip()
    fallback_model_name = (os.getenv("OFFLINE_LLM_MODEL_NAME_FALLBACK") or "").strip()
    primary_effective = (offline_model_name or model or _DEFAULT_OPENAI_COMPAT_MODEL).strip()
    chat_url = _resolve_acord_chat_completions_url()
    offline_tok = (os.getenv("OFFLINE_LLM_AUTH_TOKEN") or "").strip()
    if not use_offline and not api_key:
        # RunPod vLLM: VL + chat URL + bearer token (no OpenAI key) is valid.
        if not (
            chat_url
            and offline_tok
            and _acord_vl_enabled()
            and is_vl_model_id(primary_effective)
        ):
            return {}
    vl_images: list[str] = []
    if _acord_vl_enabled() and uir.layout:
        raw = uir.layout.get("acord_vl_page_images_base64")
        if isinstance(raw, list):
            vl_images = [str(x) for x in raw if isinstance(x, str) and x.strip()]

    acroform_flat = _acroform_flat_from_uir(uir)

    # ── Primary: Qwen2.5-VL on vLLM (OpenAI chat) — required for vision+text; /generate is not used for VL. ──
    if (
        _acord_vl_enabled()
        and is_vl_model_id(primary_effective)
        and chat_url
        and (api_key or offline_tok)
    ):
        small_model = (
            _is_small_extraction_model(model)
            or _is_small_extraction_model(offline_model_name)
            or strict_llama8b_only
        )
        kv_cap = int(os.getenv("ACORD_EXTRACT_MAX_KV_SMALL", "140")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_KV", "300"))
        table_cap = int(os.getenv("ACORD_EXTRACT_MAX_TABLES_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TABLES", "30"))
        text_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS_SMALL", "12000")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS", "32000"))
        text_blocks_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS", "20"))
        max_new_tokens = (
            int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS_SMALL", "2048"))
            if small_model
            else int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS", "4096"))
        )
        attempts = max(1, int(os.getenv("ACORD_EXTRACT_RETRIES", "3")))
        key_values = [kv.model_dump() for kv in uir.key_values[:kv_cap]]
        tables = [t.model_dump() for t in uir.tables[:table_cap]]
        text = "\n".join(tb.text for tb in uir.text_blocks[:text_blocks_cap])[:text_cap]
        schema_hint = _small_model_schema_hint() if small_model else _SCHEMA_HINT
        hint_line = (
            f"USER-SELECTED FORM TYPE: ACORD {form_type_hint.strip()} "
            f"— prioritise ACORD {form_type_hint.strip()} extraction rules.\n\n"
            if form_type_hint
            else ""
        )
        out = await _vl_chat_extract_with_retries(
            url=chat_url,
            api_key=api_key,
            model=(offline_model_name or primary_effective),
            hint_line=hint_line,
            schema_hint=schema_hint,
            key_values=key_values,
            tables=tables,
            text=text,
            images_b64=vl_images,
            max_tokens=max_new_tokens,
            attempts=attempts,
            acroform_flat=acroform_flat or None,
        )
        if out:
            logger.info(
                "ACORD extraction used primary VL model via chat (images=%s)",
                len(vl_images),
            )
            return _finalize_llm_json_with_acroform(
                uir,
                _stamp_llm_json_with_response_source(out, _structured_source_label_for_chat_url(chat_url)),
            )
        if fallback_model_name and not is_vl_model_id(fallback_model_name) and (offline_url or chat_url):
            # When primary VL fails, try the text-only fallback.
            # - If a RunPod/vLLM `/generate` endpoint exists: use it (smaller payload, historically working).
            # - Otherwise fall back to the same OpenAI-compatible chat endpoint (lets you run both
            #   models from a single vLLM server that only exposes chat).
            fb: dict[str, Any] = {}

            if offline_url:
                logger.warning(
                    "ACORD primary VL model returned no JSON; trying fallback text model via /generate (%s)",
                    fallback_model_name,
                )
                fb = await _offline_extract_with_retries(
                    model=fallback_model_name,
                    prompt_builder=lambda correction: _build_extraction_prompt(
                        hint_line=hint_line,
                        schema_hint=schema_hint,
                        key_values=key_values,
                        tables=tables,
                        text=text,
                        correction=correction,
                        acroform_flat=acroform_flat or None,
                    ),
                    attempts=attempts,
                    max_tokens=max_new_tokens,
                )
            if (not fb) and chat_url:
                logger.warning(
                    "ACORD primary VL model returned no JSON; trying fallback text model via chat endpoint (%s)",
                    fallback_model_name,
                )
                fb = await _vl_chat_extract_with_retries(
                    url=chat_url,
                    api_key=api_key,
                    model=fallback_model_name,
                    hint_line=hint_line,
                    schema_hint=schema_hint,
                    key_values=key_values,
                    tables=tables,
                    text=text,
                    images_b64=[],  # text-only fallback has no page-image inputs
                    max_tokens=max_new_tokens,
                    attempts=attempts,
                    acroform_flat=acroform_flat or None,
                )

            if fb:
                if offline_url:
                    lbl = _structured_source_label_for_offline_generate_url(offline_url)
                    if _url_looks_like_runpod(offline_url):
                        lbl = f"{lbl} (fallback text model after VL returned no JSON)"
                else:
                    lbl = _structured_source_label_for_chat_url(chat_url)
                return _finalize_llm_json_with_acroform(
                    uir,
                    _stamp_llm_json_with_response_source(fb, lbl),
                )
        logger.warning("ACORD VL primary failed and no usable fallback produced JSON.")
        return {}

    if _acord_vl_enabled() and is_vl_model_id(primary_effective) and not chat_url:
        logger.warning(
            "OFFLINE_LLM_MODEL_NAME is a VL model but RUNPOD_OPENAI_COMPAT_URL (or OPENAI_CHAT_COMPLETIONS_URL) "
            "is not set — vLLM chat is required for Qwen2.5-VL. Trying fallback text-only /generate if configured."
        )
        if fallback_model_name and offline_url:
            small_model = _is_small_extraction_model(fallback_model_name) or strict_llama8b_only
            kv_cap = int(os.getenv("ACORD_EXTRACT_MAX_KV_SMALL", "140")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_KV", "300"))
            table_cap = int(os.getenv("ACORD_EXTRACT_MAX_TABLES_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TABLES", "30"))
            text_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS_SMALL", "12000")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS", "32000"))
            text_blocks_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS", "20"))
            max_new_tokens = (
                int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS_SMALL", "2048"))
                if small_model
                else int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS", "4096"))
            )
            attempts = max(1, int(os.getenv("ACORD_EXTRACT_RETRIES", "3")))
            key_values = [kv.model_dump() for kv in uir.key_values[:kv_cap]]
            tables = [t.model_dump() for t in uir.tables[:table_cap]]
            text = "\n".join(tb.text for tb in uir.text_blocks[:text_blocks_cap])[:text_cap]
            schema_hint = _small_model_schema_hint() if small_model else _SCHEMA_HINT
            hint_line = (
                f"USER-SELECTED FORM TYPE: ACORD {form_type_hint.strip()} "
                f"— prioritise ACORD {form_type_hint.strip()} extraction rules.\n\n"
                if form_type_hint
                else ""
            )
            fb = await _offline_extract_with_retries(
                model=fallback_model_name,
                prompt_builder=lambda correction: _build_extraction_prompt(
                    hint_line=hint_line,
                    schema_hint=schema_hint,
                    key_values=key_values,
                    tables=tables,
                    text=text,
                    correction=correction,
                    acroform_flat=acroform_flat or None,
                ),
                attempts=attempts,
                max_tokens=max_new_tokens,
            )
            if fb:
                return _finalize_llm_json_with_acroform(
                    uir,
                    _stamp_llm_json_with_response_source(
                        fb,
                        _structured_source_label_for_offline_generate_url(offline_url),
                    ),
                )
        return {}

    def _label_for_standard_extract_path() -> str:
        if _acord_use_offline_generate((api_key or "").strip()):
            return _structured_source_label_for_offline_generate_url(_acord_offline_generate_url())
        return _structured_source_label_for_chat_url(url)

    small_model = (
        _is_small_extraction_model(model)
        or _is_small_extraction_model(offline_model_name)
        or strict_llama8b_only
    )
    kv_cap = int(os.getenv("ACORD_EXTRACT_MAX_KV_SMALL", "140")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_KV", "300"))
    table_cap = int(os.getenv("ACORD_EXTRACT_MAX_TABLES_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TABLES", "30"))
    text_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS_SMALL", "12000")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_CHARS", "32000"))
    text_blocks_cap = int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS_SMALL", "12")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TEXT_BLOCKS", "20"))
    max_tokens = int(os.getenv("ACORD_EXTRACT_MAX_TOKENS_SMALL", "1400")) if small_model else int(os.getenv("ACORD_EXTRACT_MAX_TOKENS", "4096"))
    # For non-small models, respect the dedicated max-new-tokens setting.
    # Previously this incorrectly used `max_tokens`, making generation much longer than intended.
    # ACORD JSON can be large (esp. merged PDF + coverages); 1536 often truncates on RunPod /generate.
    max_new_tokens = (
        int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS_SMALL", "2048"))
        if small_model
        else int(os.getenv("ACORD_EXTRACT_MAX_NEW_TOKENS", "4096"))
    )
    attempts = max(1, int(os.getenv("ACORD_EXTRACT_RETRIES", "3")))

    key_values = [kv.model_dump() for kv in uir.key_values[:kv_cap]]
    tables = [t.model_dump() for t in uir.tables[:table_cap]]
    text = "\n".join(tb.text for tb in uir.text_blocks[:text_blocks_cap])[:text_cap]
    schema_hint = _small_model_schema_hint() if small_model else _SCHEMA_HINT

    # Prepend user-selected form type so the model focuses on the right schema
    hint_line = (
        f"USER-SELECTED FORM TYPE: ACORD {form_type_hint.strip()} "
        f"— prioritise ACORD {form_type_hint.strip()} extraction rules.\n\n"
        if form_type_hint else ""
    )
    use_multi_pass = small_model and (os.getenv("ACORD_EXTRACT_MULTI_PASS", "true").strip().lower() in {"1", "true", "yes", "on"})
    if use_multi_pass and len(uir.text_blocks) > text_blocks_cap:
        window_size = max(4, int(os.getenv("ACORD_EXTRACT_SMALL_WINDOW_BLOCKS", str(text_blocks_cap))))
        stride = max(2, int(os.getenv("ACORD_EXTRACT_SMALL_WINDOW_STRIDE", str(max(2, window_size // 2)))))
        merged: dict[str, Any] = {}
        pass_count = 0
        for start in range(0, len(uir.text_blocks), stride):
            subset = uir.text_blocks[start: start + window_size]
            if not subset:
                break
            pass_text = "\n".join(tb.text for tb in subset)[:text_cap]
            pass_count += 1
            partial = await _extract_with_retries(
                url=url,
                api_key=api_key,
                model=model,
                hint_line=hint_line,
                schema_hint=schema_hint,
                key_values=key_values,
                tables=tables,
                text=pass_text,
                max_tokens=max_new_tokens,
                attempts=attempts,
                acroform_flat=acroform_flat or None,
            )
            if partial:
                merged = _merge_extraction_dicts(merged, partial)
            if start + window_size >= len(uir.text_blocks):
                break
        logger.info("ACORD extraction multi-pass complete: passes=%s merged_keys=%s", pass_count, len(merged.keys()))
        if merged:
            return _finalize_llm_json_with_acroform(
                uir,
                _stamp_llm_json_with_response_source(merged, _label_for_standard_extract_path()),
            )

    raw = await _extract_with_retries(
        url=url,
        api_key=api_key,
        model=model,
        hint_line=hint_line,
        schema_hint=schema_hint,
        key_values=key_values,
        tables=tables,
        text=text,
        max_tokens=max_new_tokens,
        attempts=attempts,
        acroform_flat=acroform_flat or None,
    )
    if not raw:
        return _finalize_llm_json_with_acroform(uir, raw)
    return _finalize_llm_json_with_acroform(
        uir,
        _stamp_llm_json_with_response_source(raw, _label_for_standard_extract_path()),
    )


def _pick_kv(uir: UnifiedIntermediateRepresentation, field: str) -> Optional[KeyValue]:
    variants = LABELS.get(field, [])
    for kv in uir.key_values:
        if any(_norm(kv.key) == _norm(v) for v in variants):
            return kv
    return None


def _kv(uir: UnifiedIntermediateRepresentation, field: str) -> Optional[str]:
    kv = _pick_kv(uir, field)
    return kv.value if kv else None


def _bool_val(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "yes", "x", "1"}
    return None


def _extract_block_after_label_from_text(text: str, label: str, *, max_lines: int = 5) -> Optional[str]:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    label_u = (label or "").strip().upper()
    if not label_u:
        return None
    for idx, ln in enumerate(lines):
        if not ln:
            continue
        ln_u = _norm(ln)
        # Only treat true label rows as anchors. Avoid matching disclaimer sentences
        # that happen to contain words like "producer" or "insured".
        if not re.match(rf"^{re.escape(label_u)}(\b|[\s:/-])", ln_u):
            # "NAMED INSURED" row when searching for insured block
            if not (label_u == "INSURED" and re.match(r"^NAMED\s+INSURED(\b|[\s:/-])", ln_u)):
                continue
        # Same-line value, e.g. "PRODUCER: ABC Agency"
        if re.match(r"^NAMED\s+INSURED(\b|[\s:/-])", ln_u):
            same_line = re.sub(r"^.*?\bNAMED\s+INSURED\b[:\s-]*", "", ln, flags=re.IGNORECASE).strip()
        else:
            same_line = re.sub(rf".*?\b{re.escape(label_u)}\b[:\s-]*", "", ln_u, flags=re.IGNORECASE).strip()
        if same_line and same_line.upper() not in {"INSURED", "PRODUCER"}:
            if not _is_suspicious_name(same_line):
                return same_line.title()
        # Next non-empty line fallback.
        for j in range(idx + 1, min(len(lines), idx + 1 + max_lines)):
            cand = (lines[j] or "").strip()
            if not cand:
                continue
            cand_u = _norm(cand)
            if cand_u in {"INSURED", "PRODUCER", "COVERAGES", "CERTIFICATE HOLDER"}:
                continue
            if len(cand_u) < 3:
                continue
            if len(cand_u) > 120:
                continue
            if any(tok in cand_u for tok in {"THIS CERTIFICATE", "NOTWITHSTANDING", "SHOULD ANY", "ACCORDANCE WITH THE POLICY"}):
                continue
            if _is_suspicious_name(cand):
                continue
            return cand
    return None


_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_AMOUNT_RE = re.compile(r"^\$?[\d,]+$")
_POLICY_RE = re.compile(r"^[A-Z]{1,5}[-\s]?\d[\d\-]{4,20}$")


def _is_valid_date(v: Optional[str]) -> bool:
    """Return True if v looks like a real MM/DD/YYYY date."""
    if not v:
        return False
    v = v.strip()
    if not _DATE_RE.match(v):
        return False
    try:
        from datetime import datetime
        datetime.strptime(v, "%m/%d/%Y")
        return True
    except ValueError:
        return False


def _clean_dollar(v: Optional[str]) -> Optional[str]:
    """Normalise a dollar amount — return None if it doesn't look like money."""
    if not v:
        return None
    v = v.strip()
    if not re.match(r"^\$?[\d,]+(\.\d+)?$", v):
        return None
    if not v.startswith("$"):
        v = "$" + v
    return v


_POLICY_NUMBER_HEADER_RE = re.compile(
    r"^(LIMITS|POLICY\s*NUMBER|TYPE\s+OF\s+INSURANCE|SCHEDULE|COVERAGE|POLIC(?:Y|IES)|N/A|NA)$",
    re.IGNORECASE,
)


def _sanitize_policy_number(v: Optional[str]) -> Optional[str]:
    """Drop table headers and labels mis-read as policy numbers (e.g. 'LIMITS', 'POLICY')."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    su = _norm(s)
    if su in {"POLICY", "POLICIES", "COVERAGE", "COVERAGES", "LIMITS", "TYPE", "INSURANCE", "SCHEDULE"}:
        return None
    if _POLICY_NUMBER_HEADER_RE.match(s):
        return None
    if not re.search(r"\d", s):
        return None
    return s


def _sanitize_certificate_number(v: Optional[str]) -> Optional[str]:
    """Keep cert id only; strip 'REVISION NUMBER: 1' tails glued from layout."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    parts = re.split(r"\s+(?:REVISION|REV\.?)\s*(?:NUMBER)?\s*:?\s*", s, maxsplit=1, flags=re.IGNORECASE)
    s = parts[0].strip()
    m = re.match(r"^([A-Z0-9][A-Z0-9\-]{3,40})", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s or None


def _postprocess_llm_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and clean LLM-extracted values:
    - Reject dates that aren't valid MM/DD/YYYY.
    - Reject dollar amounts that are clearly wrong (e.g. 'LIMITS').
    - Reject policy numbers that are clearly form labels.
    - Strip leading/trailing whitespace from all string leaves.
    """
    if not isinstance(data, dict):
        return data

    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out[k] = _postprocess_llm_json(v)
        elif isinstance(v, list):
            out[k] = [_postprocess_llm_json(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, str):
            v = v.strip()
            # Validate date fields
            if any(d in k.lower() for d in ("_date", "effective", "expiration", "eff", "exp")):
                out[k] = v if _is_valid_date(v) else None
            # Validate / normalise dollar amounts
            elif any(d in k.lower() for d in ("limit", "premium", "amount", "aggregate", "occurrence", "damage", "injury")):
                out[k] = _clean_dollar(v) if v else None
            # Reject policy numbers that look like form labels (e.g. LIMITS column)
            elif k == "policy_number":
                out[k] = _sanitize_policy_number(v)
            # Strip ACORD 25 legend / footer text mis-labeled as entity names
            elif k == "name":
                out[k] = v if (v and not _is_suspicious_name(v)) else None
            else:
                out[k] = v or None
        else:
            out[k] = v
    return out


def _looks_like_certificate_boilerplate_name(v: str) -> bool:
    """
    ACORD 25 footer / legend text often bleeds into producer or insured name fields:
    leading commas, 'CERTIFICATE HOLDER', policy(ies) sentences, etc.
    """
    s = (v or "").strip()
    if not s:
        return False
    su = _norm(s)
    t = s.lstrip()
    if t.startswith((",", ";")):
        return True
    if len(su) > 100:
        return True
    if len(su.split()) >= 12:
        return True
    needles = (
        "CERTIFICATE HOLDER",
        "ADDITIONAL INSURED PROVISIONS",
        "THE POLICY(IES)",
        "POLICY(IES) MUST",
        "MUST HAVE",
        "SUBJECT TO THE",
        "AND THE CERTIFICATE HOLDER",
        "SUBROGATION IS WAIVED",
        "IF SUBROGATION",
        "BE ENDORSED",
        "OR BE ENDORSED",
    )
    if any(n in su for n in needles):
        return True
    # Short fragment glued from legend row
    if re.match(r"^,?\s*AND\s+THE\s+CERTIFICATE\s+HOLDER", su):
        return True
    return False


def _is_suspicious_name(v: Optional[str]) -> bool:
    s = (v or "").strip()
    if not s:
        return True
    if _looks_like_certificate_boilerplate_name(s):
        return True
    su = _norm(s)
    bad_exact = {
        "INSURED",
        "PRODUCER",
        "NOT",
        "N/A",
        "NA",
        "LIMITS",
        "COVERAGES",
        "CERTIFICATE HOLDER",
        # ACORD 25: column / section titles mis-read as holder or insured
        "CANCELLATION",
        "ENTITY TYPE:",
        "ENTITY TYPE",
        # ACORD 125 column-header rows that pdfplumber sometimes picks up as values
        "NAIC CODE CARRIER",
        "GL CODE SIC NAICS",
        "UNDERWRITER UNDERWRITER OFFICE",
        "QUOTE ISSUE POLICY RENEW",
        "NAMED INSURED AND MAILING ADDRESS",
    }
    if su in bad_exact:
        return True
    if len(su) <= 2:
        return True
    # Form row labels (ACORD 25 entity-type line, email-only producer bleed)
    if su.startswith("ENTITY TYPE"):
        return True
    if su.startswith("EMAIL:") or su.startswith("E-MAIL:"):
        return True
    if _looks_like_us_city_state_zip_line(s):
        return True
    # Common ACORD sentence bleed-through indicates malformed extraction.
    if "SUBROGATION" in su or "ENDORSEMENT" in su or "NOTWITHSTANDING" in su:
        return True
    # If the value starts with any known form-label prefix it's a header, not a real value.
    _FORM_LABEL_PREFIXES = (
        "GL CODE",
        "NAIC CODE",
        "NAICS",
        "SIC NAICS",
        "FEIN OR SOC",
        "UNDERWRITER",
        "QUOTE ISSUE",
        "CANCEL PM",
        "NAMED INSURED AND MAILING",
        "AGENCY CUSTOMER",
        "ENTITY TYPE",
        "CONTACT NAME",
    )
    for prefix in _FORM_LABEL_PREFIXES:
        if su.startswith(prefix):
            return True
    # String made entirely of ALL-CAPS words with no lowercase → likely a form header
    words = su.split()
    if len(words) >= 4 and all(w.isupper() or not w.isalpha() for w in words):
        return True
    return False


def _is_suspicious_description_of_operations(v: Optional[str]) -> bool:
    """Reject form question rows / checkbox labels mis-labeled as narrative description."""
    s = (v or "").strip()
    if not s:
        return True
    # "ANY AREA LEASED TO OTHERS? Y / N" and similar — not a description of operations
    if re.search(r"\?\s*Y\s*/\s*N", s, flags=re.IGNORECASE):
        return True
    if "?" in s and len(s) < 160 and re.search(r"\bY\s*/\s*N\b", s, flags=re.IGNORECASE):
        return True
    if s.upper().startswith("ANY ") and "?" in s:
        return True
    # ACORD 25 table section title, not narrative "description of operations"
    su = s.upper().strip()
    if su in {"LOCATIONS / VEHICLES", "LOCATIONS/VEHICLES"} or (
        "LOCATIONS" in su and "VEHICLES" in su and len(s) < 48
    ):
        return True
    return False


def build_summary_from_uir(
    uir: UnifiedIntermediateRepresentation,
    llm_json: dict[str, Any] | None = None,
) -> AcordFormSummary:
    llm = dict(llm_json or {})
    structured_response_source = llm.pop(ACORD_STRUCTURED_RESPONSE_SOURCE_KEY, None)
    if structured_response_source is None and not llm:
        structured_response_source = "Fallback response"
    base = _base_conf(uir)          # engine-aware base confidence for this extraction
    llm_conf = base * 0.95          # LLM-derived fields (slight discount vs layout KV)

    # ── Producer ──────────────────────────────────────────────────────────────
    raw_text_all = "\n".join(tb.text for tb in uir.text_blocks).strip()
    p = llm.get("producer") or {}
    kv_prod = _pick_kv(uir, "producer")
    prod_name = p.get("name") or (kv_prod.value if kv_prod else None)
    if _is_suspicious_name(prod_name):
        prod_name = _extract_block_after_label_from_text(raw_text_all, "PRODUCER") or prod_name
    if _is_suspicious_name(prod_name):
        prod_name = None

    i = llm.get("insured") or {}
    kv_ins = _pick_kv(uir, "insured")
    ins_name = i.get("name") or (kv_ins.value if kv_ins else None)
    if _is_suspicious_name(ins_name):
        ins_name = _extract_block_after_label_from_text(raw_text_all, "INSURED") or ins_name
    if _is_suspicious_name(ins_name):
        ins_name = None

    prod_name, ins_name, prod_rx, ins_rx = _apply_acord25_regex_name_fallback(
        raw_text_all,
        llm.get("form_type"),
        prod_name,
        ins_name,
    )
    prod_name_conf = (
        REGEX_NAME_FALLBACK_CONF
        if prod_rx
        else (kv_prod.confidence if (kv_prod and prod_name) else (llm_conf if prod_name else 0.0))
    )
    insured_name_conf = (
        REGEX_NAME_FALLBACK_CONF
        if ins_rx
        else (kv_ins.confidence if (kv_ins and ins_name) else (llm_conf if ins_name else 0.0))
    )

    # Deterministic two-column PRODUCER / INSURED line (ACORD 25 certificate layout).
    if ac25fb.is_acord25_text(raw_text_all):
        p2, i2 = ac25fb.two_column_producer_insured(raw_text_all)
        if p2 and (not prod_name or _is_suspicious_name(prod_name)):
            prod_name = p2
            prod_name_conf = ACORD25_DETERMINISTIC_NAME_CONF
        if i2 and (not ins_name or _is_suspicious_name(ins_name)):
            ins_name = i2
            insured_name_conf = ACORD25_DETERMINISTIC_NAME_CONF
    # ACORD 125 application: agency / first named insured lines (layout varies — conservative).
    elif ac125fb.is_acord125_text(raw_text_all):
        if not prod_name or _is_suspicious_name(prod_name):
            ap = ac125fb.agency_first_line(raw_text_all)
            if ap:
                prod_name = ap
                prod_name_conf = ACORD25_DETERMINISTIC_NAME_CONF
        if not ins_name or _is_suspicious_name(ins_name):
            ins = ac125fb.first_named_insured_line(raw_text_all)
            if ins:
                ins_name = ins
                insured_name_conf = ACORD25_DETERMINISTIC_NAME_CONF

    # Sanitize common label-bleed fields. If the "value" doesn't contain any digits,
    # it's almost always a form label/template fragment, not a real phone/fax.
    contact_name = p.get("contact_name") or _kv(uir, "contact_name")
    if _is_suspicious_name(contact_name):
        contact_name = None
    if (not contact_name or _is_suspicious_name(contact_name)) and ac25fb.is_acord25_text(raw_text_all):
        cn = ac25fb.contact_name_from_text(raw_text_all)
        if cn and not _is_suspicious_name(cn):
            contact_name = cn

    phone = p.get("phone") or _kv(uir, "phone")
    if phone and not re.search(r"\d", phone):
        phone = None

    fax = p.get("fax") or _kv(uir, "fax")
    if fax and not re.search(r"\d", fax):
        fax = None

    email = p.get("email") or _kv(uir, "email")
    if email and ("@" not in email):
        email = None

    agency_customer_id = p.get("agency_customer_id") or _kv(uir, "agency_customer_id")
    if _is_suspicious_name(agency_customer_id):
        agency_customer_id = None

    subcode = p.get("subcode")
    if subcode and _is_suspicious_name(subcode):
        subcode = None

    producer = AcordProducer(
        name=prod_name,
        name_confidence=prod_name_conf,
        contact_name=contact_name,
        address=p.get("address"),
        city=p.get("city"),
        state=p.get("state"),
        postal_code=p.get("postal_code"),
        phone=phone,
        fax=fax,
        email=email,
        agency_customer_id=agency_customer_id,
        subcode=subcode,
        producer_license_no=p.get("producer_license_no"),
        national_producer_number=p.get("national_producer_number"),
    )

    # ── Insured ───────────────────────────────────────────────────────────────
    insured = AcordInsured(
        name=ins_name,
        name_confidence=insured_name_conf,
        contact_name=i.get("contact_name"),
        mailing_address=i.get("mailing_address"),
        city=i.get("city"),
        state=i.get("state"),
        postal_code=i.get("postal_code"),
        phone=i.get("phone"),
        fax=i.get("fax"),
        email=i.get("email"),
        website=i.get("website"),
        entity_type=i.get("entity_type"),
        gl_code=i.get("gl_code"),
        sic=i.get("sic"),
        naics=i.get("naics"),
        fein=i.get("fein"),
    )

    # ── Other named insureds ──────────────────────────────────────────────────
    other_named: list[AcordOtherNamedInsured] = []
    for oi in (llm.get("other_named_insureds") or []):
        if not isinstance(oi, dict):
            continue
        other_named.append(AcordOtherNamedInsured(
            name=oi.get("name"),
            mailing_address=oi.get("mailing_address"),
            city=oi.get("city"),
            state=oi.get("state"),
            postal_code=oi.get("postal_code"),
            phone=oi.get("phone"),
            website=oi.get("website"),
            entity_type=oi.get("entity_type"),
            gl_code=oi.get("gl_code"),
            sic=oi.get("sic"),
            naics=oi.get("naics"),
            fein=oi.get("fein"),
        ))

    # ── Holder ────────────────────────────────────────────────────────────────
    h = llm.get("holder") or {}
    holder: Optional[AcordHolder] = None
    kv_hold = _kv(uir, "holder")
    holder_name = h.get("name") if isinstance(h, dict) else None
    if not holder_name:
        # _kv(...) returns a plain string in this pipeline; keep backward-safe handling
        # in case older callers return objects with a `.value` attribute.
        if isinstance(kv_hold, str):
            holder_name = kv_hold
        else:
            holder_name = getattr(kv_hold, "value", None) if kv_hold else None
    # Only run label-heuristic when we already have a bad non-empty value — otherwise it can latch onto the wrong row.
    if holder_name and _is_suspicious_name(holder_name):
        holder_name = _extract_block_after_label_from_text(raw_text_all, "CERTIFICATE HOLDER") or holder_name
    if _is_suspicious_name(holder_name):
        holder_name = None
    if (not holder_name or _is_suspicious_name(holder_name)) and ac25fb.is_acord25_text(raw_text_all):
        hn = ac25fb.certificate_holder_name(raw_text_all)
        if hn:
            holder_name = hn
    if holder_name or (isinstance(h, dict) and (h.get("address") or h.get("city") or h.get("state") or h.get("postal_code"))):
        holder = AcordHolder(
            name=holder_name,
            address=h.get("address") if isinstance(h, dict) else None,
            city=h.get("city") if isinstance(h, dict) else None,
            state=h.get("state") if isinstance(h, dict) else None,
            postal_code=h.get("postal_code") if isinstance(h, dict) else None,
            is_additional_insured=_bool_val(h.get("is_additional_insured")) if isinstance(h, dict) else None,
            is_subrogation_waived=_bool_val(h.get("is_subrogation_waived")) if isinstance(h, dict) else None,
        )

    # ── Policy info (ACORD 125) ───────────────────────────────────────────────
    pi = llm.get("policy_info") or {}
    policy_info: Optional[AcordPolicyInfo] = None
    if pi:
        carrier_d = pi.get("carrier") or {}
        policy_info = AcordPolicyInfo(
            carrier=AcordCarrier(name=carrier_d.get("name"), naic_number=carrier_d.get("naic_number")) if carrier_d else None,
            program_name=pi.get("program_name") or _kv(uir, "program_name"),
            program_code=pi.get("program_code"),
            policy_number=_sanitize_policy_number(pi.get("policy_number") or _kv(uir, "policy_number")),
            proposed_eff_date=pi.get("proposed_eff_date"),
            proposed_exp_date=pi.get("proposed_exp_date"),
            billing_plan=pi.get("billing_plan") or _kv(uir, "billing_plan"),
            payment_plan=pi.get("payment_plan") or _kv(uir, "payment_plan"),
            method_of_payment=pi.get("method_of_payment"),
            deposit=pi.get("deposit"),
            minimum_premium=pi.get("minimum_premium"),
            policy_premium=pi.get("policy_premium"),
            transaction_type=pi.get("transaction_type"),
            transaction_date=pi.get("transaction_date"),
            underwriter=pi.get("underwriter") or _kv(uir, "underwriter"),
            underwriter_office=pi.get("underwriter_office"),
        )

    # ── Lines of business indicated ───────────────────────────────────────────
    lob_indicated: list[str] = []
    for item in (llm.get("lines_of_business_indicated") or []):
        if isinstance(item, str) and item.strip():
            lob_indicated.append(item.strip())

    # ── Certificate-style coverage blocks ────────────────────────────────────
    coverages: list[AcordPolicyCoverage] = []
    for item in (llm.get("coverages") or [])[:20]:
        if not isinstance(item, dict):
            continue
        eff = _parse_date_any(str(item.get("effective_date") or ""))
        exp = _parse_date_any(str(item.get("expiration_date") or ""))
        pn = _sanitize_policy_number(item.get("policy_number"))
        ins_list: list[AcordCarrier] = []
        for ins in (item.get("insurers") or [])[:10]:
            if isinstance(ins, dict):
                ins_list.append(AcordCarrier(name=ins.get("name"), naic_number=ins.get("naic_number")))
        coverages.append(AcordPolicyCoverage(
            line_of_business=item.get("line_of_business"),
            block_confidence=llm_conf,
            policy_number=pn,
            policy_number_confidence=llm_conf if pn else 0.0,
            effective_date=eff,
            effective_date_confidence=llm_conf if eff else 0.0,
            expiration_date=exp,
            expiration_date_confidence=llm_conf if exp else 0.0,
            claims_made=_bool_val(item.get("claims_made")),
            occurrence_type=_bool_val(item.get("occurrence_type")),
            additional_insured=_bool_val(item.get("additional_insured")),
            waiver_of_subrogation=_bool_val(item.get("waiver_of_subrogation")),
            each_occurrence=item.get("each_occurrence"),
            damage_to_rented_premises=item.get("damage_to_rented_premises"),
            medical_expense=item.get("medical_expense"),
            personal_advertising_injury=item.get("personal_advertising_injury"),
            general_aggregate=item.get("general_aggregate"),
            products_comp_ops_aggregate=item.get("products_comp_ops_aggregate"),
            combined_single_limit=item.get("combined_single_limit"),
            bodily_injury_per_person=item.get("bodily_injury_per_person"),
            bodily_injury_per_accident=item.get("bodily_injury_per_accident"),
            property_damage=item.get("property_damage"),
            occurrence_limit=item.get("occurrence_limit"),
            aggregate_limit=item.get("aggregate_limit"),
            deductible=item.get("deductible"),
            retention=item.get("retention"),
            retroactive_date=item.get("retroactive_date"),
            wc_statutory_limits=_bool_val(item.get("wc_statutory_limits")),
            employer_liability_each_accident=item.get("employer_liability_each_accident"),
            employer_liability_each_employee=item.get("employer_liability_each_employee"),
            employer_liability_policy_limit=item.get("employer_liability_policy_limit"),
            insurers=ins_list,
        ))

    # KV fallback when LLM returned no coverages
    if not coverages:
        kv_pol = _pick_kv(uir, "policy_number")
        kv_eff = _pick_kv(uir, "effective_date")
        kv_exp = _pick_kv(uir, "expiration_date")
        eff = _parse_date_any(kv_eff.value) if kv_eff else None
        exp = _parse_date_any(kv_exp.value) if kv_exp else None
        pn_kv = _sanitize_policy_number(kv_pol.value if kv_pol else None)
        if kv_pol or kv_eff or kv_exp:
            coverages.append(AcordPolicyCoverage(
                line_of_business=None,
                block_confidence=base * 0.6,   # KV-only fallback = lower confidence
                policy_number=pn_kv,
                policy_number_confidence=(kv_pol.confidence if (kv_pol and pn_kv) else 0.0),
                effective_date=eff,
                effective_date_confidence=kv_eff.confidence if (kv_eff and eff) else 0.0,
                expiration_date=exp,
                expiration_date_confidence=kv_exp.confidence if (kv_exp and exp) else 0.0,
            ))

    def _acord25_coverages_broken(covs: list[AcordPolicyCoverage]) -> bool:
        if not covs:
            return True
        good = 0
        for c in covs:
            pn = _sanitize_policy_number(getattr(c, "policy_number", None))
            if pn:
                good += 1
        return good == 0

    # Deterministic policy rows + insurer lines when LLM returns headers (e.g. "LIMITS") or empty.
    if ac25fb.is_acord25_text(raw_text_all) and _acord25_coverages_broken(coverages):
        rows = ac25fb.coverage_policy_rows(raw_text_all)
        ins_lines = ac25fb.insurer_lines(raw_text_all)
        if rows:
            coverages = []
            det_conf = ACORD25_DETERMINISTIC_NAME_CONF * 0.98
            for idx, row in enumerate(rows[:12]):
                eff = ac25fb.parse_mmddyyyy(str(row.get("effective_date") or ""))
                exp = ac25fb.parse_mmddyyyy(str(row.get("expiration_date") or ""))
                pn = _sanitize_policy_number(row.get("policy_number"))
                ins_list: list[AcordCarrier] = []
                if idx < len(ins_lines):
                    ins_list.append(
                        AcordCarrier(
                            name=ins_lines[idx]["name"],
                            naic_number=ins_lines[idx]["naic"],
                        )
                    )
                coverages.append(
                    AcordPolicyCoverage(
                        line_of_business=row.get("line_of_business"),
                        block_confidence=det_conf,
                        policy_number=pn,
                        policy_number_confidence=det_conf if pn else 0.0,
                        effective_date=eff,
                        effective_date_confidence=det_conf if eff else 0.0,
                        expiration_date=exp,
                        expiration_date_confidence=det_conf if exp else 0.0,
                        insurers=ins_list,
                    )
                )

    # ── Premises ──────────────────────────────────────────────────────────────
    premises: list[AcordPremises] = []
    for pr in (llm.get("premises") or []):
        if not isinstance(pr, dict):
            continue
        premises.append(AcordPremises(
            location_number=pr.get("location_number"),
            street=pr.get("street"),
            city=pr.get("city"),
            state=pr.get("state"),
            county=pr.get("county"),
            zip=pr.get("zip"),
            interest=pr.get("interest"),
            full_time_employees=pr.get("full_time_employees"),
            part_time_employees=pr.get("part_time_employees"),
            annual_revenues=pr.get("annual_revenues"),
            total_building_area_sqft=pr.get("total_building_area_sqft"),
            description_of_operations=pr.get("description_of_operations"),
            area_leased_to_others=pr.get("area_leased_to_others"),
        ))

    # ── Prior carriers ────────────────────────────────────────────────────────
    prior_carriers: list[AcordPriorCarrier] = []
    for pc in (llm.get("prior_carriers") or []):
        if not isinstance(pc, dict):
            continue
        prior_carriers.append(AcordPriorCarrier(
            year=pc.get("year"),
            category=pc.get("category"),
            carrier=pc.get("carrier"),
            policy_number=pc.get("policy_number"),
            premium=pc.get("premium"),
            effective_date=pc.get("effective_date"),
            expiration_date=pc.get("expiration_date"),
        ))

    # ── Loss history ──────────────────────────────────────────────────────────
    loss_history: list[AcordLossHistory] = []
    for lh in (llm.get("loss_history") or []):
        if not isinstance(lh, dict):
            continue
        loss_history.append(AcordLossHistory(
            date_of_occurrence=lh.get("date_of_occurrence"),
            line_type=lh.get("line_type"),
            description=lh.get("description"),
            date_of_claim=lh.get("date_of_claim"),
            amount_paid=lh.get("amount_paid"),
            amount_reserved=lh.get("amount_reserved"),
            subrogation=_bool_val(lh.get("subrogation")),
            claim_open=_bool_val(lh.get("claim_open")),
        ))

    # ── Additional interests ──────────────────────────────────────────────────
    additional_interests: list[AcordAdditionalInterest] = []
    for ai in (llm.get("additional_interests") or []):
        if not isinstance(ai, dict):
            continue
        additional_interests.append(AcordAdditionalInterest(
            interest_type=ai.get("interest_type"),
            name=ai.get("name"),
            address=ai.get("address"),
            location=ai.get("location"),
            building=ai.get("building"),
            loan_reference=ai.get("loan_reference"),
        ))

    # ── Form type ─────────────────────────────────────────────────────────────
    form_type = llm.get("form_type")
    if not form_type:
        joined = "\n".join(tb.text for tb in uir.text_blocks[:5])
        m = re.search(r"ACORD\s+(\d+)", joined, flags=re.IGNORECASE)
        form_type = f"ACORD {m.group(1)}" if m else None

    # ── Cancellation days ─────────────────────────────────────────────────────
    cancel_raw = llm.get("cancellation_notice_days")
    cancellation_days: Optional[int] = None
    if cancel_raw is not None:
        try:
            cancellation_days = int(cancel_raw)
        except (TypeError, ValueError):
            pass
    if cancellation_days is None and ac25fb.is_acord25_text(raw_text_all):
        cancellation_days = ac25fb.cancellation_days(raw_text_all)

    # ── Extraction metadata ───────────────────────────────────────────────────
    meta_raw = llm.get("extraction_meta") or {}
    # Build server-side not_applicable list based on detected form type
    server_not_applicable: list[str] = []
    if form_type and "125" in form_type:
        # ACORD 125 is an application — no holder, no cancellation notice
        if not holder:
            server_not_applicable.append("holder")
        server_not_applicable.append("cancellation_notice_days")
    elif form_type and "25" in form_type and "125" not in form_type:
        # ACORD 25 certificate — no policy_info, other_named_insureds, premises, prior_carriers
        for f in ["policy_info", "other_named_insureds", "premises", "prior_carriers"]:
            server_not_applicable.append(f)

    llm_not_applicable = [x for x in (meta_raw.get("not_applicable_to_form_type") or []) if isinstance(x, str)]
    combined_not_applicable = sorted(set(server_not_applicable + llm_not_applicable))

    extraction_engine = (uir.layout or {}).get("extraction_engine", "unknown")
    _lay = uir.layout or {}
    pdf_form_classification = _lay.get("pdf_form_classification") if isinstance(_lay.get("pdf_form_classification"), str) else None
    ocr_text_engine = _lay.get("ocr_engine_used") if isinstance(_lay.get("ocr_engine_used"), str) else None
    remarks_list: list[str] = [x for x in (meta_raw.get("remarks") or []) if isinstance(x, str)]
    if pdf_form_classification == "flattened":
        remarks_list.append(
            "PDF has no AcroForm fields (flattened/print layout). "
            "OCR text and VL page images drive extraction; verify checkboxes and multi-page tables.",
        )

    # ── Suppress all-null empty objects (holder with every field null) ─────────
    # This avoids cluttering the output with useless {"name": null, "city": null ...} blocks
    def _is_all_null(obj: Any) -> bool:
        if obj is None:
            return True
        if hasattr(obj, "model_dump"):
            d = obj.model_dump()
            return all(
                v is None or (isinstance(v, list) and len(v) == 0)
                for v in d.values()
            )
        return False

    if _is_all_null(holder):
        holder = None

    # ── Confidence roll-up — all extracted objects contribute ────────────────
    confs: list[float] = []

    # Core identity fields (highest weight — count twice)
    for v in [producer.name_confidence, insured.name_confidence]:
        if v is not None:
            confs.extend([float(v), float(v)])

    # Coverage blocks
    for c in coverages:
        for v in [c.block_confidence, c.policy_number_confidence,
                  c.effective_date_confidence, c.expiration_date_confidence]:
            if v is not None:
                confs.append(float(v))

    # policy_info presence bonus — if we have carrier + policy number, reward it
    if policy_info:
        has_carrier = bool(policy_info.carrier and policy_info.carrier.name)
        has_policy_num = bool(policy_info.policy_number)
        has_dates = bool(policy_info.proposed_eff_date and policy_info.proposed_exp_date)
        pi_score = (
            (0.8 if has_carrier else 0.3)
            + (0.85 if has_policy_num else 0.3)
            + (0.8 if has_dates else 0.3)
        ) / 3
        confs.append(pi_score)

    # Other named insureds — each one has an address → confidence signal
    for oi in other_named:
        confs.append(0.75 if oi.name else 0.3)

    # Premises
    for pr in premises:
        confs.append(0.7 if (pr.street or pr.city) else 0.3)

    # Prior carriers
    for pc in prior_carriers:
        confs.append(0.7 if pc.carrier else 0.3)

    overall = sum(confs) / len(confs) if confs else 0.0
    # Clamp to [0, 1]
    overall = max(0.0, min(1.0, overall))

    if overall < 0.3 and base > 0.7:
        remarks_list.append(
            "Structured fields are sparse despite strong PDF/text extraction (base_confidence). "
            "Overall score reflects missing producer/insured names and policy details, not OCR or merge quality.",
        )

    extraction_meta = ExtractionMeta(
        form_type_detected=meta_raw.get("form_type_detected") or form_type,
        blank_in_document=[x for x in (meta_raw.get("blank_in_document") or []) if isinstance(x, str)],
        not_applicable_to_form_type=combined_not_applicable,
        all_checked_items=[x for x in (meta_raw.get("all_checked_items") or []) if isinstance(x, str)],
        remarks=remarks_list,
        extraction_engine=extraction_engine,
        base_confidence=round(base, 4),
        structured_response_source=structured_response_source,
        pdf_form_classification=pdf_form_classification,
        ocr_text_engine=ocr_text_engine,
    )

    desc_ops = llm.get("description_of_operations") or _kv(uir, "description_of_operations")
    if _is_suspicious_description_of_operations(desc_ops):
        desc_ops = None
    if (not desc_ops) and ac25fb.is_acord25_text(raw_text_all):
        desc_ops = ac25fb.description_of_operations(raw_text_all)

    raw_text = "\n".join(tb.text for tb in uir.text_blocks).strip()

    return AcordFormSummary(
        form_type=form_type,
        form_version=llm.get("form_version"),
        certificate_number=_sanitize_certificate_number(
            llm.get("certificate_number") or _kv(uir, "certificate_number"),
        ),
        revision_date=llm.get("revision_date"),
        date=llm.get("date"),
        producer=producer,
        insured=insured,
        other_named_insureds=other_named,
        holder=holder,
        policy_info=policy_info,
        lines_of_business_indicated=lob_indicated,
        coverages=coverages,
        premises=premises,
        prior_carriers=prior_carriers,
        loss_history=loss_history,
        additional_interests=additional_interests,
        description_of_operations=desc_ops,
        nature_of_business=llm.get("nature_of_business"),
        cancellation_notice_days=cancellation_days,
        additional_remarks=llm.get("additional_remarks"),
        extra_fields=llm.get("extra_fields") or None,
        extraction_meta=extraction_meta,
        overall_confidence=overall,
        raw_text=raw_text,
    )
