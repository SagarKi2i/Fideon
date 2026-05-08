from __future__ import annotations

from typing import Dict, List


SCHEMA_REGISTRY: Dict[str, List[str]] = {
    "acord_25": [
        "producer",
        "insured_name",
        "insured_address",
        "policy_number",
        "effective_date",
        "expiration_date",
        "carrier",
    ],
    "acord_27": [
        "producer",
        "insured_name",
        "vehicle_description",
        "vin",
        "policy_number",
        "effective_date",
        "expiration_date",
        "carrier",
    ],
    "acord_80": [
        "agency_name",
        "insured_name",
        "property_address",
        "carrier",
        "policy_number",
        "effective_date",
        "expiration_date",
    ],
    "acord_85": [
        "agency_name",
        "insured_name",
        "carrier",
        "policy_number",
        "property_limit",
        "effective_date",
        "expiration_date",
    ],
    "acord_90": [
        "agency_name",
        "insured_name",
        "policy_number",
        "premium",
        "effective_date",
        "expiration_date",
        "carrier",
    ],
    "acord_125": [
        "agency_name",
        "contact_name",
        "carrier",
        "policy_number",
        "email",
        "phone",
        "lines_of_business",
    ],
    "acord_126": [
        "agency_name",
        "insured_name",
        "business_description",
        "carrier",
        "policy_number",
        "effective_date",
        "expiration_date",
    ],
    "acord_140": [
        "agency_name",
        "insured_name",
        "vehicle_year_make_model",
        "vin",
        "policy_number",
        "carrier",
        "effective_date",
        "expiration_date",
    ],
}


FIELD_ALIASES: Dict[str, List[str]] = {
    "insured_name": ["applicant_name", "named_insured"],
    "agency_name": ["producer", "agency"],
    "policy_number": ["policy_no", "policy_id"],
}

IMPORTANT_FIELDS: List[str] = ["policy_number", "insured_name", "carrier"]


def normalize_by_form(form_type: str, labels: dict) -> dict:
    schema = SCHEMA_REGISTRY.get(form_type, [])
    # Alias-to-canonical mapping for cross-form consistency.
    merged = dict(labels or {})
    for canonical, aliases in FIELD_ALIASES.items():
        if canonical in merged and merged.get(canonical) not in (None, ""):
            continue
        for alias in aliases:
            if alias in merged and merged.get(alias) not in (None, ""):
                merged[canonical] = merged.get(alias)
                break

    out = {}
    for k in schema:
        v = merged.get(k)
        if v is None:
            out[k] = None
        else:
            s = str(v).strip()
            out[k] = s if s else None
    return out


def normalize_aliases_for_schema(data: dict, form_type: str) -> dict:
    schema = SCHEMA_REGISTRY.get(form_type, [])
    merged = dict(data or {})
    for canonical, aliases in FIELD_ALIASES.items():
        if canonical in merged and merged.get(canonical) not in (None, ""):
            continue
        for alias in aliases:
            if alias in merged and merged.get(alias) not in (None, ""):
                merged[canonical] = merged.get(alias)
                break
    out = {}
    for key in schema:
        value = merged.get(key)
        if value is None:
            out[key] = None
        else:
            txt = str(value).strip()
            out[key] = txt if txt else None
    return out

