"""
Canonical ACORD form type validation.
canonical_acord_form_key() is used throughout the pipeline to normalise
form type strings before writing training samples or building datasets.
"""
from __future__ import annotations

SUPPORTED_FORM_TYPES: frozenset[str] = frozenset(
    {"25", "27", "80", "85", "90", "125", "126", "130", "140"}
)

# Human-readable names used in prompts / model cards.
FORM_TYPE_NAMES: dict[str, str] = {
    "25":  "Certificate of Liability Insurance",
    "27":  "Evidence of Property Insurance",
    "80":  "Garage Coverage Summary",
    "85":  "General Liability Application",
    "90":  "Automobile Application",
    "125": "Commercial Insurance Application",
    "126": "Commercial General Liability Section",
    "130": "Commercial Property Application",
    "140": "Property Loss Notice",
}


class UnsupportedFormTypeError(ValueError):
    pass


def canonical_acord_form_key(form_type: str) -> str:
    """
    Normalise any form_type string to its canonical numeric key.

    Examples
    --------
    "acord25"   → "25"
    "ACORD 125" → "125"
    "25"        → "25"

    Raises UnsupportedFormTypeError for unknown types.
    """
    ft = str(form_type or "").strip().lower()
    ft = ft.replace("acord", "").replace(" ", "").replace("_", "")
    if ft not in SUPPORTED_FORM_TYPES:
        raise UnsupportedFormTypeError(
            f"Form type '{form_type}' is not supported. "
            f"Supported: {sorted(SUPPORTED_FORM_TYPES)}"
        )
    return ft


def form_type_display_name(form_type: str) -> str:
    key = canonical_acord_form_key(form_type)
    return f"ACORD {key} — {FORM_TYPE_NAMES.get(key, 'Unknown')}"
