from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .schema import FIXED_SCHEMA_KEYS

try:
    from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None


def validate_json(output: str) -> Dict[str, Any] | None:
    s = (output or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(s[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
        return None


def enforce_schema(data: Dict[str, Any], schema_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    keys = schema_keys or FIXED_SCHEMA_KEYS
    fixed: Dict[str, Any] = {}
    for key in keys:
        value = data.get(key)
        if value is None:
            fixed[key] = None
            continue
        txt = str(value).strip()
        fixed[key] = txt if txt else None
    return fixed


def _fuzzy_score(value: str, text: str) -> float:
    val = value.lower()
    src = text.lower()
    if val in src:
        return 100.0
    if fuzz is not None:
        return float(fuzz.partial_ratio(val, src))
    return float(100.0 * SequenceMatcher(a=val, b=src).ratio())


def enforce_grounding(
    data: Dict[str, Any], text: str, threshold: float = 85.0, schema_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    keys = schema_keys or FIXED_SCHEMA_KEYS
    grounded = dict(data)
    for key in keys:
        value = grounded.get(key)
        if value is None:
            continue
        token = str(value).strip()
        if not token:
            grounded[key] = None
            continue
        if _fuzzy_score(token, text or "") < threshold:
            grounded[key] = None
    return grounded


def validate_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    if out.get("email") is not None:
        email = str(out["email"]).strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            out["email"] = None
    if out.get("phone") is not None:
        digits = re.sub(r"\D", "", str(out["phone"]))
        if len(digits) < 7 or len(digits) > 15:
            out["phone"] = None
    return out


def verify_field(field: str, value: Any, text: str, threshold: float = 85.0) -> Any:
    if value is None:
        return None
    token = str(value).strip()
    if not token:
        return None
    return value if _fuzzy_score(token, text or "") >= threshold else None


def compute_confidence(data: Dict[str, Any], text: str, schema_keys: Optional[List[str]] = None) -> float:
    keys = schema_keys or FIXED_SCHEMA_KEYS
    scores = []
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        token = str(value).strip()
        if not token:
            continue
        scores.append(_fuzzy_score(token, text or ""))
    return float(sum(scores) / len(scores)) if scores else 0.0


def compute_trust_score(data: Dict[str, Any], text: str, schema_keys: Optional[List[str]] = None) -> float:
    keys = schema_keys or FIXED_SCHEMA_KEYS
    total = len(keys)
    if total == 0:
        return 0.0
    source = (text or "").lower()
    score = 0.0
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        token = str(value).strip().lower()
        if token and token in source:
            score += 1.0
    return score / float(total)


def compute_field_confidence(data: Dict[str, Any], text: str, schema_keys: Optional[List[str]] = None) -> Dict[str, float]:
    keys = schema_keys or FIXED_SCHEMA_KEYS
    out: Dict[str, float] = {}
    src = text or ""
    for key in keys:
        value = data.get(key)
        if value is None:
            out[key] = 0.0
            continue
        token = str(value).strip()
        if not token:
            out[key] = 0.0
            continue
        out[key] = _fuzzy_score(token, src)
    return out


def apply_field_position_heuristics(
    data: Dict[str, Any],
    text: str,
    field_confidence: Dict[str, float],
    schema_keys: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Penalize confidence if a field appears in a suspicious region.
    ACORD 125 often has agency/contact near top section.
    """
    src = text or ""
    n = max(len(src), 1)
    adjusted = dict(field_confidence)
    keys = set(schema_keys or FIXED_SCHEMA_KEYS)
    top_fields = {"agency_name", "contact_name", "carrier"} & keys
    for key in top_fields:
        value = data.get(key)
        if value is None:
            continue
        token = str(value).strip()
        if not token:
            continue
        idx = src.lower().find(token.lower())
        if idx >= 0 and idx > int(0.65 * n):
            adjusted[key] = max(0.0, adjusted.get(key, 0.0) - 20.0)
    return adjusted


def rule_based_extraction(text: str) -> Dict[str, Any]:
    rules: Dict[str, Any] = {}
    src = text or ""

    policy_match = re.search(r"\b(?:POLICY(?:\s*(?:NO|NUMBER|#))?[:\s\-]*)?([A-Z0-9][A-Z0-9\-]{5,})\b", src, flags=re.IGNORECASE)
    if policy_match:
        token = policy_match.group(1).strip()
        if re.search(r"[A-Z]", token, flags=re.IGNORECASE) and re.search(r"\d", token):
            rules["policy_number"] = token

    email_match = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", src)
    if email_match:
        rules["email"] = email_match.group(0).strip()

    phone_match = re.search(r"(?:\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}", src)
    if phone_match:
        rules["phone"] = phone_match.group(0).strip()

    return rules


def consistency_check(data: Dict[str, Any], text: str) -> Dict[str, Any]:
    out = dict(data)
    src = (text or "").lower()

    # If carrier value is a generic label token, invalidate it.
    carrier = out.get("carrier")
    if carrier is not None:
        c = str(carrier).strip().lower()
        if c in {"carrier", "insurance", "company"}:
            out["carrier"] = None

    # Policy should appear in source text.
    pol = out.get("policy_number")
    if pol is not None:
        token = str(pol).strip().lower()
        if token and token not in src:
            out["policy_number"] = None

    # De-duplicate exact mirror values for semantically different fields.
    if out.get("agency_name") is not None and out.get("carrier") is not None:
        if str(out["agency_name"]).strip().lower() == str(out["carrier"]).strip().lower():
            out["carrier"] = None

    return out

