"""
Convert a user correction (original_fields + corrected_fields + raw_text)
into a chat-format training sample ready for SFT.

build_training_sample_from_correction() is the public entry point.
Supports any insurance document type (ACORD forms, policy dec pages,
loss run reports, certificates, binders, endorsements, etc.).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("fideon.ingest")


# ── Supported document types ───────────────────────────────────────────────────

_ACORD_NUMERIC_TYPES: frozenset[str] = frozenset(
    {"25", "27", "80", "85", "90", "125", "126", "130", "140"}
)

_NON_ACORD_TYPES: frozenset[str] = frozenset(
    {"POLICY_DEC", "CERTIFICATE", "LOSS_RUN", "BINDER",
     "ENDORSEMENT", "CLAIM_FORM", "APPLICATION", "QUOTE", "OTHER"}
)

SUPPORTED_FORM_TYPES: frozenset[str] = (
    _ACORD_NUMERIC_TYPES
    | {f"ACORD_{n}" for n in _ACORD_NUMERIC_TYPES}
    | _NON_ACORD_TYPES
)


class CorrectionValidationError(ValueError):
    pass


# ── System prompt ──────────────────────────────────────────────────────────────

def get_universal_system_prompt() -> str:
    """Universal system prompt that works for all insurance document types."""
    return (
        "You are an expert insurance document parser. "
        "Given raw OCR text from an insurance document, extract ALL fields and return "
        "a single valid JSON object. Use \"\" for blank fields. Represent checkboxes as "
        "true/false. Represent table rows as arrays of objects. Dates must be in "
        "YYYY-MM-DD format. Currency amounts must include the $ prefix. "
        "Output ONLY the JSON — no commentary, no markdown fences."
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _canonical_form_key(form_type: str) -> str:
    """
    Normalise form type to a canonical key.

    Examples
    --------
    "acord25", "ACORD_25", "25"  →  "25"
    "POLICY_DEC", "policy_dec"   →  "POLICY_DEC"
    "LOSS_RUN"                   →  "LOSS_RUN"
    """
    ft = str(form_type or "").strip()
    ft_lower = ft.lower()

    # Strip 'acord_' or 'acord' prefix → numeric ACORD type
    if ft_lower.startswith("acord_"):
        numeric = ft[6:]
        if numeric in _ACORD_NUMERIC_TYPES:
            return numeric
    elif ft_lower.startswith("acord"):
        numeric = ft[5:]
        if numeric in _ACORD_NUMERIC_TYPES:
            return numeric

    # Pure numeric ACORD type
    if ft in _ACORD_NUMERIC_TYPES:
        return ft

    # Non-ACORD type — case-insensitive match
    for known in _NON_ACORD_TYPES:
        if ft.upper() == known:
            return known

    raise CorrectionValidationError(
        f"Unsupported form type '{form_type}'. "
        f"Supported numeric ACORD: {sorted(_ACORD_NUMERIC_TYPES)}. "
        f"Supported document types: {sorted(_NON_ACORD_TYPES)}."
    )


def _user_text_prefix(doc_type: str) -> str:
    """Return a human-readable document type label for the user message."""
    if doc_type in _ACORD_NUMERIC_TYPES:
        return f"ACORD Form {doc_type}"
    if doc_type.startswith("ACORD_"):
        return f"ACORD Form {doc_type[6:]}"
    _prefixes = {
        "POLICY_DEC":  "Insurance Policy Declarations Page",
        "CERTIFICATE": "Certificate of Insurance",
        "LOSS_RUN":    "Loss Run Report",
        "BINDER":      "Insurance Binder",
        "ENDORSEMENT": "Policy Endorsement",
        "CLAIM_FORM":  "Claim Form",
        "APPLICATION": "Insurance Application",
        "QUOTE":       "Insurance Quote",
    }
    return _prefixes.get(doc_type, f"Insurance Document ({doc_type})")


def _flatten_field_values(fields: Any) -> Dict[str, Any]:
    """
    Accept fields in either flat or {value, confidence} form and return a flat dict.
    Only unwraps the immediate top-level {value: ...} wrappers; nested dicts are kept.
    Kept as a utility for callers that need explicit flattening.
    """
    if not isinstance(fields, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        # Unwrap single-value wrapper like {"value": "Acme", "confidence": "high"}
        if isinstance(v, dict) and "value" in v and set(v.keys()) <= {"value", "page", "confidence"}:
            out[k] = v["value"]
        else:
            out[k] = v
    return out


def _deep_merge(base: Any, override: Any) -> Any:
    """
    Recursively merge *override* into *base*.

    - dicts:   keys present in override win; keys only in base are kept
    - lists:   override replaces base entirely (user supplied the full list)
    - scalars: override wins
    - None / missing in base: override value used
    """
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for k, v in override.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = _deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged
    return override


def _deep_merge_base_correction(
    base_extracted: Dict[str, Any],
    corrected_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge user corrections over the original extraction.

    Corrected values take priority; keys only in base are kept.
    Supports both flat dicts (old format) and nested objects
    (new schema with value/page/confidence leaves). Partial
    corrections to a nested section don't erase sibling keys.
    """
    return _deep_merge(base_extracted, corrected_json)  # type: ignore[return-value]


def get_corrected_paths(
    original: Dict[str, Any],
    corrected: Dict[str, Any],
    prefix: str = "",
) -> List[str]:
    """
    Recursively find all dot-notation paths where *corrected* differs from *original*.

    Arrays are compared as a whole unit (not element-by-element).

    Example
    -------
    original  = {"parties": {"named_insured": "Old Name", "insurer": "X"}}
    corrected = {"parties": {"named_insured": "New Name"}}
    → ["parties.named_insured"]
    """
    paths: List[str] = []
    for key, corrected_value in corrected.items():
        path = f"{prefix}.{key}" if prefix else key
        original_value = original.get(key)
        if original_value != corrected_value:
            if isinstance(corrected_value, dict) and isinstance(original_value, dict):
                paths.extend(get_corrected_paths(original_value, corrected_value, path))
            else:
                paths.append(path)
    return paths


# ── Public entry point ─────────────────────────────────────────────────────────

def build_training_sample_from_correction(
    # Old-style positional args — kept for backward compatibility
    run_row: Optional[Dict[str, Any]] = None,
    corrected_json: Optional[Dict[str, Any]] = None,
    feedback_id: str = "",
    # New-style explicit args
    sample_id: str = "",
    upload_id: str = "",
    form_type: str = "",
    original_fields: Optional[Dict[str, Any]] = None,
    corrected_fields: Optional[Dict[str, Any]] = None,
    raw_text: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Build a training sample from a user correction.

    Supports any insurance document type:
    - ACORD forms (25, 125, 126, 130, 140, etc.)
    - Policy declarations pages  (POLICY_DEC)
    - Certificates of insurance  (CERTIFICATE)
    - Loss run reports           (LOSS_RUN)
    - Binders, endorsements, claim forms, applications, quotes

    Calling conventions
    -------------------
    Old style (backward compatible — all existing callers continue to work):

        build_training_sample_from_correction(
            run_row=sample_dict,
            corrected_json={"policy_number": "GL-0123", ...},
        )

    New style (explicit args):

        build_training_sample_from_correction(
            sample_id="acord25_001",
            upload_id="pdf_abc",
            form_type="25",              # or "POLICY_DEC", "LOSS_RUN", etc.
            original_fields={...},
            corrected_fields={...},
            raw_text="...",
            docling_data={               # optional
                "markdown": "...",
                "kv_pairs": {"Key": "Value"},
                "tables":   ["| col | ..."],
            },
        )

    Returns
    -------
    {"messages": [...], "domain": "insurance", "metadata": {...}}
    Compatible with Qwen 2.5 VL fine-tuning via LLaMA-Factory.
    """
    # ── Resolve args — support both calling conventions ───────────────────────
    if run_row is not None:
        _sample_id   = run_row.get("sample_id") or sample_id
        _upload_id   = run_row.get("upload_id") or upload_id
        _form_type   = run_row.get("form_type") or form_type or "25"
        _raw_text    = str(run_row.get("raw_text") or raw_text or "").strip()
        _original    = run_row.get("original_fields") or original_fields or {}
        # Explicit corrected_json arg takes priority over stored corrected_fields
        _corrected   = corrected_json if corrected_json else (
            run_row.get("corrected_fields") or corrected_fields or {}
        )
        _feedback_id = feedback_id
    else:
        _sample_id   = sample_id
        _upload_id   = upload_id
        _form_type   = form_type or "25"
        _raw_text    = str(raw_text or "").strip()
        _original    = original_fields or {}
        _corrected   = corrected_fields or corrected_json or {}
        _feedback_id = feedback_id

    # ── Normalise document type ───────────────────────────────────────────────
    doc_type = _canonical_form_key(_form_type)

    # ── Merge original + corrections ──────────────────────────────────────────
    # Deep merge preserves nested siblings; corrected values always win.
    merged = _deep_merge_base_correction(_original, _corrected)
    if not merged:
        raise CorrectionValidationError("corrected_json produced an empty field dict")

    # ── Build user message ────────────────────────────────────────────────────
    prefix   = _user_text_prefix(doc_type)
    user_text = f"{prefix}\n\nOCR TEXT:\n{_raw_text or '(no text)'}"

    # Append optional Docling output if caller provided it
    docling_data: Optional[Dict[str, Any]] = kwargs.get("docling_data")
    if isinstance(docling_data, dict):
        if docling_data.get("markdown"):
            user_text += f"\n\nSTRUCTURED MARKDOWN:\n{docling_data['markdown']}"
        if docling_data.get("kv_pairs"):
            kv_str = "\n".join(
                f"{k}: {v}" for k, v in docling_data["kv_pairs"].items()
            )
            user_text += f"\n\nKEY-VALUE PAIRS:\n{kv_str}"
        if docling_data.get("tables"):
            tables_str = "\n\n".join(docling_data["tables"])
            user_text += f"\n\nTABLES:\n{tables_str}"

    assistant_content = json.dumps(merged, ensure_ascii=False, indent=2)

    # ── Track which fields were actually corrected (dot-notation paths) ───────
    corrected_paths = get_corrected_paths(
        _original if isinstance(_original, dict) else {},
        _corrected if isinstance(_corrected, dict) else {},
    )

    # ── Schema validation (non-blocking) ─────────────────────────────────────
    validation_errors: List[str] = []
    try:
        from insurance_schema_registry import get_registry
        _registry = get_registry()
        validation = _registry.validate(merged)
        if not validation.get("valid"):
            validation_errors = validation.get("errors", [])
            logger.warning(
                "[ingest] Training sample %s has %d validation error(s): %s",
                _sample_id or "(no id)",
                len(validation_errors),
                validation_errors[:3],
            )
    except Exception as exc:
        logger.debug("[ingest] Schema validation skipped: %s", exc)

    # ── Assemble and return ───────────────────────────────────────────────────
    metadata: Dict[str, Any] = {
        "form_type":         doc_type,
        "document_type":     doc_type,
        "upload_id":         _upload_id,
        "sample_id":         _sample_id,
        "feedback_id":       _feedback_id,
        "corrected_fields":  corrected_paths,
        "correction_source": "human_review",
        "created_at":        datetime.now(timezone.utc).isoformat(),
    }
    if validation_errors:
        metadata["validation_errors"] = validation_errors

    return {
        "messages": [
            {"role": "system",    "content": get_universal_system_prompt()},
            {"role": "user",      "content": user_text},
            {"role": "assistant", "content": assistant_content},
        ],
        "domain": "insurance",
        "metadata": metadata,
    }
