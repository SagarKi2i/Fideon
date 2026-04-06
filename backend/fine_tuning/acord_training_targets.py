"""
Clean nested ACORD extraction JSON and map to flat SFT labels used by quality gate eval.

Pipeline DB rows use AcordFormSummary-shaped JSON (producer, policy_info, …).
Fine-tuning eval expects FIXED_SCHEMA_KEYS from acord_form_pipeline.schema.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

# Removed from top-level label dict before recursive cleaning (not form fields).
TOP_LEVEL_STRIP = [
    "extraction_meta",
    "overall_confidence",
    "form_version",
    "raw_text",
    "hardened_inference",
]

LIST_DEDUP_FIELDS = [
    "lines_of_business_indicated",
    "all_checked_items",
]


def _strip_confidence_keys_recursive(obj: Any) -> Any:
    """
    Recursively remove any key that:
    - exactly matches: overall_confidence, base_confidence
    - ends with: _confidence
    Works on nested dicts and lists.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_confidence_keys_recursive(v)
            for k, v in obj.items()
            if k not in ("overall_confidence", "base_confidence") and not k.endswith("_confidence")
        }
    if isinstance(obj, list):
        return [_strip_confidence_keys_recursive(item) for item in obj]
    return obj


def _dedupe_str_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for x in items:
        s = str(x).strip() if x is not None else ""
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def strip_pipeline_metadata(obj: Any) -> Any:
    """Drop pipeline internals and *confidence fields; recurse into dicts/lists."""
    if isinstance(obj, dict):
        new: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in TOP_LEVEL_STRIP:
                continue
            if k.endswith("_confidence"):
                continue
            new[k] = strip_pipeline_metadata(v)
        return new
    if isinstance(obj, list):
        return [strip_pipeline_metadata(x) for x in obj]
    return obj


def dedupe_indicated_lists(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Deduplicate known list fields (order-preserving)."""
    out = dict(extracted)
    for k in LIST_DEDUP_FIELDS:
        if k in out:
            out[k] = _dedupe_str_list(out.get(k))
    em = out.get("extraction_meta")
    if isinstance(em, dict):
        em = dict(em)
        if "all_checked_items" in em:
            em["all_checked_items"] = _dedupe_str_list(em.get("all_checked_items"))
        out["extraction_meta"] = em
    return out


def normalize_list_vs_null(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convention: empty list -> [] (never null for list-typed sections).
    Optional scalars stay null when missing (handled at leaf level by exporters).
    """
    # Only touch known list fields on the summary object.
    list_keys = (
        "lines_of_business_indicated",
        "other_named_insureds",
        "coverages",
        "premises",
        "prior_carriers",
        "loss_history",
        "additional_interests",
    )
    out = dict(extracted)
    for k in list_keys:
        if k not in out:
            continue
        v = out[k]
        if v is None:
            out[k] = []
        elif isinstance(v, list):
            out[k] = v
        else:
            out[k] = [v] if v else []
    return out


def flatten_acord_summary_to_six_fields(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map nested AcordFormSummary JSON to flat keys matching FIXED_SCHEMA_KEYS.
    Prefer explicit top-level keys when present; else producer / policy_info.
    """
    from fine_tuning.acord_form_pipeline.schema import FIXED_SCHEMA_KEYS

    out: Dict[str, Any] = {}
    for key in FIXED_SCHEMA_KEYS:
        v = extracted.get(key)
        if v is not None and str(v).strip():
            out[key] = v

    prod = extracted.get("producer")
    if isinstance(prod, dict):
        if not out.get("agency_name"):
            out["agency_name"] = prod.get("name")
        if not out.get("contact_name"):
            out["contact_name"] = prod.get("contact_name")
        if not out.get("email"):
            out["email"] = prod.get("email")
        if not out.get("phone"):
            out["phone"] = prod.get("phone")

    pol = extracted.get("policy_info")
    if isinstance(pol, dict):
        if not out.get("policy_number"):
            out["policy_number"] = pol.get("policy_number")
        if not out.get("carrier"):
            car = pol.get("carrier")
            if isinstance(car, dict):
                out["carrier"] = car.get("name")
            elif isinstance(car, str):
                out["carrier"] = car

    return {k: out.get(k) for k in FIXED_SCHEMA_KEYS}


def build_sft_label_json(extracted_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip metadata and confidence keys, dedupe list fields, then six-field flatten + normalize_label.
    """
    from fine_tuning.acord_form_pipeline.schema import normalize_label

    if not isinstance(extracted_raw, dict):
        extracted_raw = {}

    result = copy.deepcopy(extracted_raw)

    for key in TOP_LEVEL_STRIP:
        result.pop(key, None)

    result = _strip_confidence_keys_recursive(result)

    for field in LIST_DEDUP_FIELDS:
        if field in result and isinstance(result[field], list):
            result[field] = list(dict.fromkeys(result[field]))

    cleaned = normalize_list_vs_null(result)
    flat = flatten_acord_summary_to_six_fields(cleaned)
    return normalize_label(flat)


if __name__ == "__main__":
    # --- _strip_confidence_keys_recursive ---
    test_doc = {
        "insured": {"name": "Acme", "name_confidence": 0.9},
        "producer": {"name": "Agency", "name_confidence": 0.8},
        "overall_confidence": 0.85,
        "policy_info": {"base_confidence": 0.7, "carrier": {"name": "XYZ"}},
    }
    cleaned = _strip_confidence_keys_recursive(test_doc)
    assert "overall_confidence" not in cleaned
    assert "base_confidence" not in cleaned["policy_info"]
    assert "name_confidence" not in cleaned["insured"]
    assert "name_confidence" not in cleaned["producer"]
    assert cleaned["insured"]["name"] == "Acme"
    assert cleaned["policy_info"]["carrier"]["name"] == "XYZ"

    # --- build_sft_label_json: no metadata / confidence in six-field output ---
    test_record = {
        "date": "07/11/2025",
        "extraction_meta": {"ocr_text_engine": "tesseract"},
        "overall_confidence": 0.81,
        "form_version": "2016/03",
        "insured": {"name": "Acme", "name_confidence": 0.9},
        "producer": {"name": "Agency Co", "name_confidence": 0.8},
        "policy_info": {"policy_number": "PN-1", "carrier": {"name": "CarrierX", "name_confidence": 0.5}},
    }
    out = build_sft_label_json(test_record)
    assert "extraction_meta" not in out
    assert "overall_confidence" not in out
    assert "form_version" not in out
    for k in out:
        assert not k.endswith("_confidence")
    assert out.get("agency_name") == "Agency Co"
    assert out.get("policy_number") == "PN-1"
    assert out.get("carrier") == "CarrierX"

    # --- LOB dedupe (same steps as inside build_sft_label_json, before flatten) ---
    lob_record = {
        "lines_of_business_indicated": ["CRIME", "UMBRELLA", "CRIME", "TRUCKERS", "UMBRELLA"],
        "producer": {"name": "P"},
        "policy_info": {"policy_number": "1", "carrier": {"name": "C"}},
    }
    r = copy.deepcopy(lob_record)
    for key in TOP_LEVEL_STRIP:
        r.pop(key, None)
    r = _strip_confidence_keys_recursive(r)
    for field in LIST_DEDUP_FIELDS:
        if field in r and isinstance(r[field], list):
            r[field] = list(dict.fromkeys(r[field]))
    lob = r["lines_of_business_indicated"]
    assert len(lob) == len(set(lob)), f"duplicates remain ({len(lob)} items, {len(set(lob))} unique)"
    assert lob == ["CRIME", "UMBRELLA", "TRUCKERS"]

    print("acord_training_targets self-tests: OK")
