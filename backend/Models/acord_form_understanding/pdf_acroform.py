"""
Fillable PDF (AcroForm) field extraction — ground-truth values without LLM hallucination.

Use when carriers export ACORD with named fields (e.g. NamedInsured_FullName_A).
Flattened / print-only PDFs (e.g. ReportLab) return {} — the pipeline falls back to VL/text LLM.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Any

logger = logging.getLogger("fideon.acord.pdf_acroform")


def _pdf_value_to_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        if hasattr(v, "get_object"):
            v = v.get_object()
    except Exception:
        pass
    s = str(v).strip()
    if s.startswith("/") and len(s) > 1:
        s = s[1:].strip()
    return s


def extract_acroform_fields(pdf_bytes: bytes) -> dict[str, str]:
    """
    Return flat mapping of PDF AcroForm field name → string value.
    Empty dict if no fields or library missing.
    """
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except ImportError:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            logger.debug("PyPDF2/pypdf not available — skipping AcroForm extraction")
            return {}

    reader = PdfReader(BytesIO(pdf_bytes))
    fields = reader.get_fields()
    if not fields:
        return {}

    out: dict[str, str] = {}
    for name, fdef in fields.items():
        if not fdef or not isinstance(fdef, dict):
            continue
        v = fdef.get("/V")
        if v is None:
            continue
        s = _pdf_value_to_str(v)
        if s:
            out[str(name)] = s
    return out


def pdf_has_acroform_widgets(pdf_bytes: bytes) -> bool:
    """
    True if the PDF defines AcroForm fields (fillable PDF).

    Flattened / print-only exports typically have no field dictionary — extraction
    must rely on text layers, OCR, and VL page images.
    """
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except ImportError:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            return False

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        fields = reader.get_fields()
    except Exception:
        return False
    return bool(fields)


def map_acroform_to_schema_overlay(flat: dict[str, str]) -> dict[str, Any]:
    """
    Map common ACORD / carrier AcroForm naming patterns onto the LLM JSON shape.
    Unknown keys remain only under extra_fields.pdf_acroform.
    """
    overlay: dict[str, Any] = {
        "extra_fields": {"pdf_acroform": dict(flat)},
    }
    prod: dict[str, Any] = {}
    ins: dict[str, Any] = {}
    hold: dict[str, Any] = {}
    pol: dict[str, Any] = {}

    for key, val in flat.items():
        if not val:
            continue
        k = key.replace(" ", "")
        kl = k.lower()

        if re.search(r"namedinsured.*fullname", kl, re.I) or kl.endswith("namedinsured_fullname_a"):
            ins["name"] = val
        elif "namedinsured" in kl and "mail" in kl:
            ins["mailing_address"] = val
        elif "namedinsured" in kl and "city" in kl and "state" not in kl:
            ins["city"] = val
        elif "namedinsured" in kl and "state" in kl:
            ins["state"] = val
        elif "namedinsured" in kl and ("postal" in kl or "zip" in kl):
            ins["postal_code"] = val
        elif "namedinsured" in kl and "fein" in kl:
            ins["fein"] = val

        elif re.search(r"producer.*(agencyname|companyname|name)", kl, re.I) and "contact" not in kl:
            prod["name"] = val
        elif "producer" in kl and "email" in kl:
            prod["email"] = val
        elif "producer" in kl and "phone" in kl:
            prod["phone"] = val
        elif "producer" in kl and "fax" in kl:
            prod["fax"] = val
        elif "producer" in kl and "contact" in kl and "name" in kl:
            prod["contact_name"] = val

        elif "certificateholder" in kl.replace("_", "") and "name" in kl:
            hold["name"] = val
        elif "certificateholder" in kl.replace("_", "") and "address" in kl:
            hold["address"] = val

        elif "policy" in kl and "policynumber" in kl.replace("_", ""):
            pol["policy_number"] = val
        elif "policy" in kl and "effective" in kl:
            pol["proposed_eff_date"] = val
        elif "policy" in kl and "expiration" in kl:
            pol["proposed_exp_date"] = val

        elif re.search(r"certificate.*number|^certificatenumber", kl, re.I) and "holder" not in kl:
            overlay["certificate_number"] = val

    if prod:
        overlay["producer"] = prod
    if ins:
        overlay["insured"] = ins
    if hold:
        overlay["holder"] = hold
    if pol:
        overlay["policy_info"] = pol

    return overlay


def _merge_acroform_priority(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge: overlay overwrites base for non-empty values."""
    out: dict[str, Any] = dict(base)
    for k, v in (overlay or {}).items():
        cur = out.get(k)
        if isinstance(v, dict) and isinstance(cur, dict):
            out[k] = _merge_acroform_priority(cur, v)
        elif v not in (None, "", [], {}):
            out[k] = v
        elif k not in out:
            out[k] = v
    return out


def merge_acroform_into_llm_json(llm_json: dict[str, Any], flat: dict[str, str]) -> dict[str, Any]:
    """
    After LLM extraction: apply AcroForm overlay so fillable-field values win over model text.
    """
    if not flat:
        return llm_json
    overlay = map_acroform_to_schema_overlay(flat)
    merged = _merge_acroform_priority(dict(llm_json or {}), overlay)
    return merged
