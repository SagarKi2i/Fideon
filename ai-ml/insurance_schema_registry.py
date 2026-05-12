"""
insurance_schema_registry.py

Universal schema validation for extracted insurance documents.
Supports all document types produced by the universal extraction prompt.

Works alongside fine_tuning/dataset/acord_strict_models.py — this module
focuses on runtime validation of extraction output; acord_strict_models.py
focuses on training-data schema enforcement.

Public API
----------
    from insurance_schema_registry import SchemaRegistry, DocumentType

    registry = SchemaRegistry()

    doc_type = registry.detect_document_type(extracted_json)
    result   = registry.validate(extracted_json)
    fixes    = registry.suggest_corrections(extracted_json, result)
    template = registry.get_empty_template(DocumentType.ACORD_25)
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("fideon.schema_registry")


# ── Document type enum ────────────────────────────────────────────────────────

class DocumentType(Enum):
    ACORD_25    = "ACORD_25"
    ACORD_125   = "ACORD_125"
    ACORD_126   = "ACORD_126"
    ACORD_130   = "ACORD_130"
    ACORD_140   = "ACORD_140"
    POLICY_DEC  = "POLICY_DEC"
    CERTIFICATE = "CERTIFICATE"
    LOSS_RUN    = "LOSS_RUN"
    BINDER      = "BINDER"
    ENDORSEMENT = "ENDORSEMENT"
    CLAIM_FORM  = "CLAIM_FORM"
    APPLICATION = "APPLICATION"
    QUOTE       = "QUOTE"
    OTHER       = "OTHER"


# ── Field-level validators ────────────────────────────────────────────────────

def validate_policy_number(value: str) -> bool:
    """Must contain at least one letter and one digit; minimum 4 characters."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    return (
        len(s) >= 4
        and bool(re.search(r"[A-Za-z]", s))
        and bool(re.search(r"\d", s))
    )


def validate_naic_code(value: str) -> bool:
    """Must be exactly 4 or 5 digits."""
    if not value or not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\d{4,5}", value.strip()))


def validate_insurance_date(value: str) -> bool:
    """Accept MM/DD/YYYY, MM-DD-YYYY, and YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    return bool(
        re.fullmatch(r"\d{2}[/\-]\d{2}[/\-]\d{4}", s)   # MM/DD/YYYY or MM-DD-YYYY
        or re.fullmatch(r"\d{4}[/\-]\d{2}[/\-]\d{2}", s) # YYYY-MM-DD
    )


def validate_currency_amount(value: str) -> bool:
    """Must be numeric with optional $ prefix, commas, and up to 2 decimal places."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    return bool(re.fullmatch(r"\$?[\d,]+(\.\d{1,2})?", s))


def validate_phone_number(value: str) -> bool:
    """Accept any format with 7–15 digits after stripping non-numeric characters."""
    if not value or not isinstance(value, str):
        return False
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15


# Map validator name → function (used by schema field definitions)
_VALIDATORS: Dict[str, Any] = {
    "policy_number": validate_policy_number,
    "naic_code":     validate_naic_code,
    "date":          validate_insurance_date,
    "currency":      validate_currency_amount,
    "phone":         validate_phone_number,
}


# ── Base schema ───────────────────────────────────────────────────────────────
#
# Defines the universal structure every extracted document should have.
# Each section entry:
#   required          — whether the section must be present
#   fields            — dict of field_name → {required, type, validator}
#   min_fields_present— how many fields must be non-empty (default 0)
#   is_array          — True when the section value is a list of objects
#   item_fields       — field schema applied to each array item

_BASE_SCHEMA: Dict[str, Any] = {
    "document_identification": {
        "required": True,
        "fields": {
            "document_type": {"required": True},
            "page_count":    {"required": True, "type": "integer"},
        },
    },
    "parties": {
        "required": True,
        "min_fields_present": 1,
        "fields": {
            "named_insured":      {"required": False},
            "insurer":            {"required": False},
            "producer_agent":     {"required": False},
            "certificate_holder": {"required": False},
            "additional_insureds":{"required": False},
        },
    },
    "policy_identifiers": {
        "required": False,
        "fields": {
            "policy_number": {"required": False, "validator": "policy_number"},
            "naic_code":     {"required": False, "validator": "naic_code"},
            "certificate_number": {"required": False},
            "quote_number":       {"required": False},
            "claim_number":       {"required": False},
        },
    },
    "dates": {
        "required": False,
        "fields": {
            "effective_date":  {"required": False, "validator": "date"},
            "expiration_date": {"required": False, "validator": "date"},
            "issue_date":      {"required": False, "validator": "date"},
            "loss_date":       {"required": False, "validator": "date"},
        },
    },
    "addresses": {
        "required": False,
        "fields": {
            "insured_address": {"required": False},
            "mailing_address": {"required": False},
            "risk_location":   {"required": False},
        },
    },
    "coverages": {
        "required": False,
        "is_array": True,
        "item_fields": {
            "coverage_type": {"required": True},
            "limit":         {"required": False, "validator": "currency"},
            "deductible":    {"required": False, "validator": "currency"},
            "premium":       {"required": False, "validator": "currency"},
        },
    },
    "financials": {
        "required": False,
        "fields": {
            "premium_total": {"required": False, "validator": "currency"},
            "fees":          {"required": False, "validator": "currency"},
            "taxes":         {"required": False, "validator": "currency"},
            "total_amount":  {"required": False, "validator": "currency"},
        },
    },
    "additional_fields": {
        "required": False,
        "fields": {},
    },
}


# ── Document-type schema overlays ─────────────────────────────────────────────
#
# Each overlay tightens specific requirements on top of the base schema.
# Only sections / fields that differ from the base need to be listed.

_OVERLAYS: Dict[str, Dict[str, Any]] = {

    DocumentType.ACORD_25.value: {
        "parties": {
            "fields": {
                "named_insured":      {"required": True},
                "certificate_holder": {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "certificate_number": {"required": True},
                "policy_number":      {"required": False, "validator": "policy_number"},
            },
        },
        "dates": {
            "fields": {
                "effective_date":  {"required": True, "validator": "date"},
                "expiration_date": {"required": True, "validator": "date"},
            },
        },
        "coverages": {
            "required": True,
            "is_array": True,
            "item_fields": {
                "coverage_type": {"required": True},
                "limit":         {"required": True, "validator": "currency"},
            },
        },
    },

    DocumentType.ACORD_125.value: {
        "parties": {
            "fields": {
                "named_insured":  {"required": True},
                "producer_agent": {"required": True},
            },
        },
        "additional_fields": {
            "required": True,
            "expected_keys": ["applicant_info", "business_description", "prior_losses"],
        },
    },

    DocumentType.ACORD_126.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
            },
        },
        "coverages": {
            "required": True,
            "is_array": True,
            "item_fields": {
                "coverage_type": {"required": True},
                "limit":         {"required": True, "validator": "currency"},
            },
        },
    },

    DocumentType.ACORD_130.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
                "insurer":       {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "policy_number": {"required": True, "validator": "policy_number"},
            },
        },
        "dates": {
            "fields": {
                "effective_date":  {"required": True, "validator": "date"},
                "expiration_date": {"required": True, "validator": "date"},
            },
        },
    },

    DocumentType.ACORD_140.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
            },
        },
        "addresses": {
            "required": True,
            "fields": {
                "risk_location": {"required": True},
            },
        },
        "coverages": {
            "required": True,
            "is_array": True,
            "item_fields": {
                "coverage_type": {"required": True},
                "limit":         {"required": False, "validator": "currency"},
            },
        },
    },

    DocumentType.POLICY_DEC.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
                "insurer":       {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "policy_number": {"required": True, "validator": "policy_number"},
            },
        },
        "dates": {
            "fields": {
                "effective_date":  {"required": True, "validator": "date"},
                "expiration_date": {"required": True, "validator": "date"},
            },
        },
        "coverages": {
            "required": True,
            "is_array": True,
            "item_fields": {
                "coverage_type": {"required": True},
            },
        },
        "financials": {
            "required": True,
            "fields": {
                "premium_total": {"required": True, "validator": "currency"},
            },
        },
    },

    DocumentType.CERTIFICATE.value: {
        "parties": {
            "fields": {
                "named_insured":      {"required": True},
                "certificate_holder": {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "certificate_number": {"required": True},
            },
        },
        "coverages": {
            "required": True,
            "is_array": True,
            "item_fields": {
                "coverage_type": {"required": True},
                "limit":         {"required": False, "validator": "currency"},
            },
        },
    },

    DocumentType.LOSS_RUN.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
                "insurer":       {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "policy_number": {"required": True, "validator": "policy_number"},
            },
        },
        "additional_fields": {
            "required": True,
            "expected_keys": ["claims"],
            "claims_schema": {
                "required": True,
                "item_fields": {
                    "claim_number":    {"required": True},
                    "date_of_loss":    {"required": True,  "validator": "date"},
                    "status":          {"required": True},
                    "paid_amount":     {"required": False, "validator": "currency"},
                    "reserved_amount": {"required": False, "validator": "currency"},
                    "total_incurred":  {"required": False, "validator": "currency"},
                },
            },
        },
    },

    DocumentType.BINDER.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
                "insurer":       {"required": True},
            },
        },
        "dates": {
            "fields": {
                "effective_date":  {"required": True, "validator": "date"},
                "expiration_date": {"required": True, "validator": "date"},
            },
        },
    },

    DocumentType.ENDORSEMENT.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "policy_number": {"required": True, "validator": "policy_number"},
            },
        },
        "dates": {
            "fields": {
                "effective_date": {"required": True, "validator": "date"},
            },
        },
        "additional_fields": {
            "required": True,
            "expected_keys": ["endorsement_number", "description_of_change"],
        },
    },

    DocumentType.CLAIM_FORM.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
            },
        },
        "dates": {
            "fields": {
                "loss_date": {"required": True, "validator": "date"},
            },
        },
        "additional_fields": {
            "required": True,
            "expected_keys": ["claimant_name", "description_of_loss"],
        },
    },

    DocumentType.APPLICATION.value: {
        "parties": {
            "fields": {
                "named_insured":  {"required": True},
                "producer_agent": {"required": True},
            },
        },
    },

    DocumentType.QUOTE.value: {
        "parties": {
            "fields": {
                "named_insured": {"required": True},
            },
        },
        "policy_identifiers": {
            "fields": {
                "quote_number": {"required": True},
            },
        },
        "dates": {
            "fields": {
                "effective_date":  {"required": True, "validator": "date"},
                "expiration_date": {"required": True, "validator": "date"},
            },
        },
    },
}


# ── Schema merge helper ───────────────────────────────────────────────────────

def _merge_overlay(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a new schema dict with overlay values applied on top of base.
    Only the keys present in the overlay are overridden; everything else
    from base is preserved unchanged.
    """
    import copy
    merged = copy.deepcopy(base)
    for section, section_overlay in overlay.items():
        if section not in merged:
            merged[section] = copy.deepcopy(section_overlay)
            continue
        sec = merged[section]
        for key, val in section_overlay.items():
            if key == "fields" and "fields" in sec and isinstance(val, dict):
                # Field-level merge: overlay individual field defs
                for field_name, field_def in val.items():
                    sec["fields"][field_name] = field_def
            else:
                sec[key] = copy.deepcopy(val)
    return merged


# ── Auto-correction suggestions ───────────────────────────────────────────────

# Common OCR character confusions in insurance documents
_OCR_CHAR_FIXES: List[Tuple[str, str]] = [
    ("O", "0"),   # letter O confused for digit 0
    ("l", "1"),   # lowercase L confused for digit 1
    ("I", "1"),   # uppercase I confused for digit 1
    ("S", "5"),   # S confused for 5 (less common but happens on handwritten forms)
    ("B", "8"),   # B confused for 8
    ("Z", "2"),   # Z confused for 2
]


def _suggest_policy_number(value: str) -> Optional[str]:
    """
    If a policy number fails validation, try common OCR substitutions.
    Returns the corrected string if a fix makes it valid, else None.
    """
    if validate_policy_number(value):
        return None  # already valid — no suggestion needed
    # Only substitute digits in the numeric portion (after the first alpha segment)
    candidate = value.strip()
    for wrong, right in _OCR_CHAR_FIXES:
        candidate = candidate.replace(wrong, right)
    if validate_policy_number(candidate) and candidate != value.strip():
        return candidate
    return None


def _suggest_naic_code(value: str) -> Optional[str]:
    """Strip non-digit OCR noise from NAIC codes."""
    if validate_naic_code(value):
        return None
    cleaned = re.sub(r"\D", "", value.strip())
    if validate_naic_code(cleaned) and cleaned != value.strip():
        return cleaned
    return None


def _suggest_date(value: str) -> Optional[str]:
    """Convert common date formats to YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if validate_insurance_date(s):
        return None  # already valid
    # Try MM/DD/YYYY → YYYY-MM-DD
    m = re.fullmatch(r"(\d{2})[/\-](\d{2})[/\-](\d{4})", s)
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"
    return None


def _suggest_currency(value: str) -> Optional[str]:
    """Add missing $ prefix to bare numeric amounts."""
    if validate_currency_amount(value):
        return None
    s = value.strip()
    # Remove any stray letters that aren't $ and try adding $
    cleaned = re.sub(r"[^\d,.]", "", s)
    if cleaned and re.fullmatch(r"[\d,]+(\.\d{1,2})?", cleaned):
        suggestion = f"${cleaned}"
        if suggestion != s:
            return suggestion
    return None


def suggest_corrections(
    extracted_json: Dict[str, Any],
    validation_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return a dict of suggested auto-corrections for common OCR errors.
    Keys are dot-notation field paths; values are the suggested replacement strings.
    Corrections are SUGGESTIONS only — never applied automatically.

    Examples:
        "policy_identifiers.policy_number": "GL-0123"   # was "GL-O123"
        "policy_identifiers.naic_code": "20443"         # was "2O443"
        "dates.effective_date": "2026-04-01"             # was "04/01/2026"
    """
    suggestions: Dict[str, Any] = {}

    def _check(path: str, value: Any, suggest_fn: Any) -> None:
        if value and isinstance(value, str) and value.strip():
            fix = suggest_fn(value)
            if fix:
                suggestions[path] = fix

    # policy_identifiers
    pi = extracted_json.get("policy_identifiers") or {}
    _check("policy_identifiers.policy_number",     pi.get("policy_number", ""),     _suggest_policy_number)
    _check("policy_identifiers.naic_code",          pi.get("naic_code", ""),          _suggest_naic_code)
    _check("policy_identifiers.certificate_number", pi.get("certificate_number", ""), _suggest_policy_number)

    # dates
    dates = extracted_json.get("dates") or {}
    for date_field in ("effective_date", "expiration_date", "issue_date", "loss_date"):
        _check(f"dates.{date_field}", dates.get(date_field, ""), _suggest_date)

    # financials
    fins = extracted_json.get("financials") or {}
    for fin_field in ("premium_total", "fees", "taxes", "total_amount"):
        _check(f"financials.{fin_field}", fins.get(fin_field, ""), _suggest_currency)

    # coverages array
    coverages = extracted_json.get("coverages") or []
    if isinstance(coverages, list):
        for idx, cov in enumerate(coverages):
            if not isinstance(cov, dict):
                continue
            for money_field in ("limit", "deductible", "premium"):
                _check(f"coverages[{idx}].{money_field}", cov.get(money_field, ""), _suggest_currency)

    # loss run claims in additional_fields
    af = extracted_json.get("additional_fields") or {}
    claims = af.get("claims") or []
    if isinstance(claims, list):
        for idx, claim in enumerate(claims):
            if not isinstance(claim, dict):
                continue
            _check(f"additional_fields.claims[{idx}].date_of_loss",    claim.get("date_of_loss", ""),    _suggest_date)
            _check(f"additional_fields.claims[{idx}].paid_amount",      claim.get("paid_amount", ""),      _suggest_currency)
            _check(f"additional_fields.claims[{idx}].reserved_amount",  claim.get("reserved_amount", ""),  _suggest_currency)
            _check(f"additional_fields.claims[{idx}].total_incurred",   claim.get("total_incurred", ""),   _suggest_currency)

    return suggestions


# ── Empty template generator ──────────────────────────────────────────────────

def get_empty_template(doc_type: "DocumentType") -> Dict[str, Any]:
    """
    Return a properly structured empty JSON skeleton for the given document type.
    All string fields are "", all arrays are [], all integers are 0.
    """
    return {
        "document_identification": {
            "document_type": doc_type.value,
            "form_number": "",
            "edition_date": "",
            "page_count": 0,
        },
        "parties": {
            "named_insured": "",
            "insurer": "",
            "producer_agent": "",
            "certificate_holder": "",
            "additional_insureds": [],
        },
        "policy_identifiers": {
            "policy_number": "",
            "certificate_number": "",
            "quote_number": "",
            "claim_number": "",
            "naic_code": "",
        },
        "dates": {
            "effective_date": "",
            "expiration_date": "",
            "issue_date": "",
            "loss_date": "",
        },
        "addresses": {
            "insured_address": "",
            "mailing_address": "",
            "risk_location": "",
        },
        "coverages": [],
        "financials": {
            "premium_total": "",
            "fees": "",
            "taxes": "",
            "total_amount": "",
        },
        "additional_fields": {},
    }


# ── Schema registry ───────────────────────────────────────────────────────────

class SchemaRegistry:
    """
    Central registry for insurance document schemas.

    Usage:
        registry = SchemaRegistry()
        result   = registry.validate(extracted_json)
        fixes    = registry.suggest_corrections(extracted_json, result)
        template = registry.get_empty_template(DocumentType.ACORD_25)
    """

    def __init__(self) -> None:
        # Pre-build merged schemas for every known document type
        self._schemas: Dict[str, Dict[str, Any]] = {}
        for doc_type in DocumentType:
            overlay = _OVERLAYS.get(doc_type.value, {})
            self._schemas[doc_type.value] = (
                _merge_overlay(_BASE_SCHEMA, overlay) if overlay else _BASE_SCHEMA
            )

    # ── Document type detection ───────────────────────────────────────────────

    def detect_document_type(self, extracted_json: Dict[str, Any]) -> DocumentType:
        """
        Read document_identification.document_type from the extracted JSON.
        Falls back to OTHER when the field is absent or unrecognised.
        """
        raw = ""
        doc_id = extracted_json.get("document_identification")
        if isinstance(doc_id, dict):
            raw = str(doc_id.get("document_type") or "").strip().upper()

        # Normalise common spelling variants
        _aliases: Dict[str, str] = {
            "ACORD25":       "ACORD_25",
            "ACORD 25":      "ACORD_25",
            "ACORD125":      "ACORD_125",
            "ACORD 125":     "ACORD_125",
            "ACORD126":      "ACORD_126",
            "ACORD 126":     "ACORD_126",
            "ACORD130":      "ACORD_130",
            "ACORD 130":     "ACORD_130",
            "ACORD140":      "ACORD_140",
            "ACORD 140":     "ACORD_140",
            "POLICY DEC":    "POLICY_DEC",
            "DECLARATIONS":  "POLICY_DEC",
            "DEC PAGE":      "POLICY_DEC",
            "LOSS RUN":      "LOSS_RUN",
            "CLAIM FORM":    "CLAIM_FORM",
        }
        normalised = _aliases.get(raw, raw)

        try:
            return DocumentType(normalised)
        except ValueError:
            return DocumentType.OTHER

    # ── Schema retrieval ──────────────────────────────────────────────────────

    def get_schema(self, doc_type: DocumentType) -> Dict[str, Any]:
        return self._schemas.get(doc_type.value, _BASE_SCHEMA)

    # ── Core validation ───────────────────────────────────────────────────────

    def validate(self, extracted_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted_json against the schema for its detected document type.

        Returns:
            {
                "valid":            bool,
                "document_type":    str,
                "errors":           [str],   # hard failures (required fields missing / wrong type)
                "warnings":         [str],   # soft issues (format violations, unexpected values)
                "missing_required": [str],   # dot-notation paths of required fields that are absent
                "field_stats":      {        # counts for dashboard / logging
                    "total_fields_present": int,
                    "empty_fields":         int,
                    "format_errors":        int,
                }
            }
        """
        errors:           List[str] = []
        warnings:         List[str] = []
        missing_required: List[str] = []
        total_present     = 0
        empty_count       = 0
        format_errors     = 0

        if not isinstance(extracted_json, dict):
            return {
                "valid": False,
                "document_type": "UNKNOWN",
                "errors": ["extracted_json is not a dict"],
                "warnings": [],
                "missing_required": [],
                "field_stats": {"total_fields_present": 0, "empty_fields": 0, "format_errors": 0},
            }

        doc_type = self.detect_document_type(extracted_json)
        schema   = self.get_schema(doc_type)

        for section_name, section_def in schema.items():
            section_data = extracted_json.get(section_name)
            section_required = section_def.get("required", False)

            # ── Section presence check ────────────────────────────────────────
            if section_data is None:
                if section_required:
                    errors.append(f"Required section '{section_name}' is missing")
                    missing_required.append(section_name)
                continue

            # ── Array section validation ──────────────────────────────────────
            if section_def.get("is_array"):
                if not isinstance(section_data, list):
                    errors.append(f"Section '{section_name}' must be an array, got {type(section_data).__name__}")
                    continue
                if section_required and len(section_data) == 0:
                    errors.append(f"Required array section '{section_name}' is empty")
                    missing_required.append(section_name)
                    continue

                item_fields = section_def.get("item_fields", {})
                for idx, item in enumerate(section_data):
                    if not isinstance(item, dict):
                        warnings.append(f"'{section_name}[{idx}]' is not an object — skipping")
                        continue
                    for field_name, field_def in item_fields.items():
                        path  = f"{section_name}[{idx}].{field_name}"
                        value = item.get(field_name)
                        total_present += 1

                        if value is None or (isinstance(value, str) and not value.strip()):
                            empty_count += 1
                            if field_def.get("required"):
                                errors.append(f"Required field '{path}' is empty")
                                missing_required.append(path)
                        else:
                            validator_name = field_def.get("validator")
                            if validator_name and validator_name in _VALIDATORS:
                                if not _VALIDATORS[validator_name](str(value)):
                                    warnings.append(
                                        f"'{path}' has unexpected format: {str(value)!r}"
                                    )
                                    format_errors += 1
                continue

            # ── Object section validation ─────────────────────────────────────

            # min_fields_present: at least N fields in the section must be non-empty
            min_present = section_def.get("min_fields_present", 0)
            if min_present > 0 and isinstance(section_data, dict):
                non_empty = sum(
                    1 for v in section_data.values()
                    if v is not None and (not isinstance(v, str) or v.strip())
                )
                if non_empty < min_present:
                    errors.append(
                        f"Section '{section_name}' must have at least {min_present} non-empty field(s); "
                        f"found {non_empty}"
                    )

            # Field-level checks
            fields_def = section_def.get("fields", {})
            for field_name, field_def in fields_def.items():
                path  = f"{section_name}.{field_name}"
                value = section_data.get(field_name) if isinstance(section_data, dict) else None
                total_present += 1

                # Type check (currently only "integer" supported)
                if value is not None and field_def.get("type") == "integer":
                    try:
                        int(value)
                    except (TypeError, ValueError):
                        warnings.append(f"'{path}' should be an integer, got {value!r}")
                        format_errors += 1

                if value is None or (isinstance(value, str) and not value.strip()):
                    empty_count += 1
                    if field_def.get("required"):
                        errors.append(f"Required field '{path}' is missing or empty")
                        missing_required.append(path)
                else:
                    validator_name = field_def.get("validator")
                    if validator_name and validator_name in _VALIDATORS:
                        if not _VALIDATORS[validator_name](str(value)):
                            warnings.append(
                                f"'{path}' has unexpected format: {str(value)!r}"
                            )
                            format_errors += 1

            # LOSS_RUN: validate claims array inside additional_fields
            if section_name == "additional_fields" and "claims_schema" in section_def:
                claims_schema = section_def["claims_schema"]
                claims        = section_data.get("claims") if isinstance(section_data, dict) else None
                if claims_schema.get("required") and not claims:
                    errors.append("Loss run 'additional_fields.claims' array is required but missing or empty")
                    missing_required.append("additional_fields.claims")
                elif isinstance(claims, list):
                    item_fields = claims_schema.get("item_fields", {})
                    for idx, claim in enumerate(claims):
                        if not isinstance(claim, dict):
                            continue
                        for field_name, field_def in item_fields.items():
                            path  = f"additional_fields.claims[{idx}].{field_name}"
                            value = claim.get(field_name)
                            total_present += 1
                            if value is None or (isinstance(value, str) and not value.strip()):
                                empty_count += 1
                                if field_def.get("required"):
                                    errors.append(f"Required claim field '{path}' is missing or empty")
                                    missing_required.append(path)
                            else:
                                validator_name = field_def.get("validator")
                                if validator_name and validator_name in _VALIDATORS:
                                    if not _VALIDATORS[validator_name](str(value)):
                                        warnings.append(
                                            f"'{path}' has unexpected format: {str(value)!r}"
                                        )
                                        format_errors += 1

            # Warn about expected keys that are absent (non-blocking)
            expected_keys = section_def.get("expected_keys", [])
            if expected_keys and isinstance(section_data, dict):
                for ek in expected_keys:
                    if ek not in section_data or section_data[ek] in (None, "", [], {}):
                        warnings.append(
                            f"Expected key '{section_name}.{ek}' not found — "
                            f"may indicate incomplete extraction for this document type"
                        )

        return {
            "valid":            len(errors) == 0,
            "document_type":    doc_type.value,
            "errors":           errors,
            "warnings":         warnings,
            "missing_required": missing_required,
            "field_stats": {
                "total_fields_present": total_present,
                "empty_fields":         empty_count,
                "format_errors":        format_errors,
            },
        }

    # ── Convenience wrappers (delegate to module-level functions) ────────────

    def suggest_corrections(
        self,
        extracted_json: Dict[str, Any],
        validation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return suggest_corrections(extracted_json, validation_result)

    def get_empty_template(self, doc_type: DocumentType) -> Dict[str, Any]:
        return get_empty_template(doc_type)


# ── Module-level singleton ────────────────────────────────────────────────────
# Import and reuse this rather than constructing a new SchemaRegistry per call.

_registry: Optional[SchemaRegistry] = None


def get_registry() -> SchemaRegistry:
    """Return the module-level SchemaRegistry singleton (created on first call)."""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry
