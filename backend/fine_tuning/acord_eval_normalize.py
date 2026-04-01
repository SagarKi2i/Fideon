"""
Normalization for eval comparison: fuzzy dates/money, strip nulls, dedupe lists, lowercase strings.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_DATE_NUMERIC = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_US = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_MONEY = re.compile(r"[^\d.]")


def _normalize_money(s: str) -> str:
    t = _MONEY.sub("", s)
    if not t:
        return ""
    try:
        return f"{float(t):.2f}"
    except ValueError:
        return s.lower().strip()


def _normalize_date_like(s: str) -> str:
    s = s.strip()
    m = _DATE_NUMERIC.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DATE_US.match(s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    low = s.lower()
    for month, num in (
        ("january", "01"),
        ("february", "02"),
        ("march", "03"),
        ("april", "04"),
        ("may", "05"),
        ("june", "06"),
        ("july", "07"),
        ("august", "08"),
        ("september", "09"),
        ("october", "10"),
        ("november", "11"),
        ("december", "12"),
    ):
        if month in low:
            dm = re.search(r"(\d{1,2}),?\s+(\d{4})", low)
            if dm:
                return f"{dm.group(2)}-{num}-{int(dm.group(1)):02d}"
    return s.lower().strip()


def normalize_scalar_for_compare(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if _DATE_NUMERIC.match(s) or _DATE_US.match(s) or any(
            m in s.lower() for m in ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
        ):
            return _normalize_date_like(s)
        if "$" in s or re.search(r"\d", s) and any(x in s for x in ("$", ",", ".")):
            return _normalize_money(s)
        return s.lower()
    if isinstance(v, list):
        return dedupe_list([normalize_scalar_for_compare(x) for x in v])
    if isinstance(v, dict):
        return normalize_for_comparison_dict(v)
    return v


def dedupe_list(items: List[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for x in items:
        key = json.dumps(x, sort_keys=True) if not isinstance(x, (str, int, float, bool, type(None))) else str(x)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def normalize_for_comparison_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys whose value is null; recurse; normalize scalars."""
    if not isinstance(d, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            inner = normalize_for_comparison_dict(v)
            if inner:
                out[k] = inner
        elif isinstance(v, list):
            nv = dedupe_list([normalize_scalar_for_compare(x) for x in v])
            if nv:
                out[k] = nv
        else:
            nv = normalize_scalar_for_compare(v)
            if nv is not None:
                out[k] = nv
    return out


ACORD_STRUCTURE_KEYS = frozenset(
    {
        "insured",
        "producer",
        "policy_info",
        "coverages",
        "premises",
        "loss_history",
        "other_named_insureds",
        "lines_of_business_indicated",
    }
)


def oos_refusal_match(predicted: str) -> bool:
    """
    True if model output looks like a valid refusal (OOS / not ACORD 125).
    Lenient: exact JSON, structural refusal, minimal JSON, or plain-text refusal.
    """
    if not predicted or not str(predicted).strip():
        return False

    s = str(predicted).strip()

    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            return False

        if obj.get("error") == "not_acord_125":
            return True

        if "error" in obj and obj.get("extracted") is None:
            return True

        if not ACORD_STRUCTURE_KEYS.intersection(obj.keys()):
            return True

        return False

    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    lower = s.lower()
    refusal_phrases = (
        "not an acord",
        "not acord 125",
        "cannot extract",
        "not a valid acord",
        "no acord fields",
        "does not appear to be",
        "unable to extract",
        "not a form",
        "not an insurance",
    )
    return any(phrase in lower for phrase in refusal_phrases)


def score_oos_batch(predicted_outputs: List[str]) -> Dict[str, Any]:
    results = [oos_refusal_match(p) for p in predicted_outputs]
    n = len(results)
    if n == 0:
        return {
            "refusal_accuracy_percent": 0.0,
            "refusal_count": 0,
            "hallucination_count": 0,
            "total_oos": 0,
        }
    ok = sum(1 for r in results if r)
    return {
        "refusal_accuracy_percent": round(100.0 * ok / n, 2),
        "refusal_count": ok,
        "hallucination_count": n - ok,
        "total_oos": n,
    }


def normalize_for_comparison_json_str(raw: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse JSON string; return (normalized_dict, error_reason)."""
    s = (raw or "").strip()
    if not s:
        return None, "empty"
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                return None, "invalid_json"
        else:
            return None, "invalid_json"
    if not isinstance(obj, dict):
        return None, "not_object"
    return normalize_for_comparison_dict(obj), None
