"""
Convert a user correction (original_fields + corrected_fields + raw_text)
into a chat-format training sample ready for SFT.

build_training_sample_from_correction() is the public entry point.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ── Supported form types ───────────────────────────────────────────────────────

SUPPORTED_FORM_TYPES = {"25", "27", "80", "85", "90", "125", "126", "130", "140"}

SYSTEM_PROMPT = (
    "You are an expert insurance document parser specialising in ACORD forms. "
    "Given raw OCR text from an ACORD form, extract ALL fields and return a single "
    "valid JSON object. Use \"\" for blank fields. Represent checkboxes as true/false. "
    "Represent table rows as arrays of objects. Output ONLY the JSON — no commentary."
)


class CorrectionValidationError(ValueError):
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _canonical_form_key(form_type: str) -> str:
    """Normalise form type to canonical key, e.g. 'acord25' → '25'."""
    ft = str(form_type or "").strip().lower()
    if ft.startswith("acord"):
        ft = ft[5:]
    if ft not in SUPPORTED_FORM_TYPES:
        raise CorrectionValidationError(
            f"Unsupported form type '{form_type}'. "
            f"Supported: {sorted(SUPPORTED_FORM_TYPES)}"
        )
    return ft


def _flatten_field_values(fields: Any) -> Dict[str, Any]:
    """
    Accept corrected_fields in either flat or {value, confidence} form and
    return a flat dict of {field_name: value}.
    """
    if not isinstance(fields, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        if isinstance(v, dict) and "value" in v:
            out[k] = v["value"]
        else:
            out[k] = v
    return out


def _deep_merge_base_correction(
    base_extracted: Dict[str, Any],
    corrected_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge user corrections over the original extraction.
    Corrected values take priority; keys only in base are kept.
    """
    merged = dict(base_extracted)
    flat_corrections = _flatten_field_values(corrected_json)
    for k, v in flat_corrections.items():
        merged[k] = v
    return merged


# ── Public entry point ─────────────────────────────────────────────────────────

def build_training_sample_from_correction(
    run_row: Dict[str, Any],
    corrected_json: Dict[str, Any],
    feedback_id: str = "",
) -> Dict[str, Any]:
    """
    Convert one training_samples.jsonl record into a chat-format SFT sample.

    Parameters
    ----------
    run_row       : one row from /workspace/training_samples.jsonl
                    Keys used: raw_text, original_fields, corrected_fields, form_type
    corrected_json: the user-edited field dict (may override run_row corrected_fields)
    feedback_id   : optional link back to a feedback record

    Returns
    -------
    {"messages": [...], "domain": "insurance", "metadata": {...}}
    """
    form_type = _canonical_form_key(run_row.get("form_type") or "25")
    raw_text   = str(run_row.get("raw_text") or "").strip()
    original   = _flatten_field_values(run_row.get("original_fields") or {})

    # User-supplied corrected_json wins over stored corrected_fields
    if corrected_json:
        merged = _deep_merge_base_correction(original, corrected_json)
    else:
        merged = _deep_merge_base_correction(
            original, run_row.get("corrected_fields") or {}
        )

    if not merged:
        raise CorrectionValidationError("corrected_json produced an empty field dict")

    user_content = (
        f"ACORD Form {form_type}\n\n"
        f"OCR TEXT:\n{raw_text or '(no text)'}"
    )
    assistant_content = json.dumps(merged, ensure_ascii=False, indent=2)

    return {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
        "domain": "insurance",
        "metadata": {
            "form_type":   form_type,
            "upload_id":   run_row.get("upload_id", ""),
            "sample_id":   run_row.get("sample_id", ""),
            "feedback_id": feedback_id,
            "created_at":  datetime.now(timezone.utc).isoformat(),
        },
    }
