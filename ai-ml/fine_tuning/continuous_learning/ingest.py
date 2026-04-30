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
    "You are an expert insurance document parser. "
    "Given raw OCR text from an insurance document, extract all fields. "
    "Output exactly three sections in order: "
    "FIELDS: (a JSON object of all extracted fields), "
    "RAW TEXT: (the source OCR text), "
    "MARKDOWN: (a summary table). "
    "No commentary outside these sections."
)


class CorrectionValidationError(ValueError):
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _canonical_form_key(form_type: str) -> str:
    """Normalise form type to canonical key, e.g. 'acord25', 'ACORD_25', 'acord_25' → '25'."""
    ft = str(form_type or "").strip().lower()
    # Strip 'acord_' or 'acord' prefix (handles ACORD_25, ACORD_125, acord25, etc.)
    if ft.startswith("acord_"):
        ft = ft[6:]
    elif ft.startswith("acord"):
        ft = ft[5:]
    if ft not in SUPPORTED_FORM_TYPES:
        # Default to "25" so the sample is never silently dropped due to an
        # unrecognised form type — a bad form type is not a reason to skip training.
        print(f"[ingest] Unknown form type '{form_type}' — defaulting to '25'")
        ft = "25"
    return ft


def _flatten_field_values(fields: Any, _prefix: str = "") -> Dict[str, Any]:
    """
    Recursively flatten nested Qwen schema into a flat {field_name: value} dict.

    Handles three shapes:
      {"named_insured": "ABC"}                          → flat string values (old format)
      {"named_insured": {"value": "ABC", ...}}          → one-level leaf nodes
      {"parties": {"named_insured": {"value": "ABC"}}}  → deep nested groups (new format)
    """
    if not isinstance(fields, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        full_key = f"{_prefix}.{k}" if _prefix else k
        if isinstance(v, dict):
            if "value" in v:
                # Leaf node: {"value": "...", "confidence": "...", "page": N}
                out[full_key] = v["value"]
            else:
                # Group node — recurse
                out.update(_flatten_field_values(v, _prefix=full_key))
        elif isinstance(v, list):
            if v:
                import json as _json
                out[full_key] = _json.dumps(v, ensure_ascii=False)
        elif v is not None:
            out[full_key] = v
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
        f"SURYA OCR TEXT (all pages):\n{raw_text or '(no text)'}"
    )
    fields_json = json.dumps(merged, ensure_ascii=False, indent=2)
    # Assistant output matches the exact format _parse_qwen_output() expects:
    # FIELDS: {json}  RAW TEXT: {ocr}  MARKDOWN: {summary}
    # Without this, fine-tuning teaches the model to drop the FIELDS: marker,
    # breaking the inference parser.
    assistant_content = (
        f"FIELDS:\n{fields_json}\n\n"
        f"RAW TEXT:\n{raw_text or ''}\n\n"
        f"MARKDOWN:\n"
        f"# ACORD Form {form_type} — Extracted Fields\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        + "".join(f"| {k} | {v} |\n" for k, v in list(merged.items())[:30])
    )

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
