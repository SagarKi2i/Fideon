"""
Deterministic ACORD 25 extraction from raw text when LLM/KV return label bleed or empty JSON.

Targets the common layout: PRODUCER INSURED header → two company names on one line,
CERTIFICATE HOLDER block, DESCRIPTION OF OPERATIONS, policy number + date rows, INSURER A–F lines.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional


def is_acord25_text(text: str) -> bool:
    u = (text or "").upper()
    return "ACORD 25" in u or "CERTIFICATE OF LIABILITY INSURANCE" in u


def two_column_producer_insured(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Line immediately after 'PRODUCER INSURED' often contains both agency and named insured:
    'Westfield Insurance Partners, LLC Apex Construction Group, Inc.'
    """
    m = re.search(r"PRODUCER\s+INSURED\s*\n\s*([^\n]+)", text, re.I)
    if not m:
        return None, None
    line = m.group(1).strip()
    if len(line) > 320:
        line = line[:320]
    if ", LLC " in line:
        a, b = line.split(", LLC ", 1)
        prod = (a.strip() + ", LLC").strip()
        ins = b.strip()
        if prod and ins and len(ins) > 3:
            return prod, ins
    if ", L.L.C. " in line:
        a, b = line.split(", L.L.C. ", 1)
        prod = (a.strip() + ", L.L.C.").strip()
        ins = b.strip()
        if prod and ins:
            return prod, ins
    return None, None


def contact_name_from_text(text: str) -> Optional[str]:
    m = re.search(r"CONTACT\s+NAME\s*:?\s*([^\n]+)", text, re.I)
    if not m:
        return None
    c = m.group(1).strip()
    c = re.split(r"\s+FEIN\b", c, maxsplit=1, flags=re.I)[0].strip()
    c = re.split(r"\s+PHONE\s*:", c, maxsplit=1, flags=re.I)[0].strip()
    if len(c) > 140 or len(c) < 2:
        return None
    return c


def certificate_holder_name(text: str) -> Optional[str]:
    m = re.search(
        r"CERTIFICATE\s+HOLDER\s+CANCELLATION\s*\r?\n\s*([^\r\n]+)",
        text,
        re.I,
    )
    if not m:
        return None
    hn = m.group(1).strip()
    hn = re.split(r"\s+SHOULD\s+ANY\b", hn, maxsplit=1, flags=re.I)[0].strip()
    hn = re.split(r"\s+SHOULD\b", hn, maxsplit=1, flags=re.I)[0].strip()
    if len(hn) < 4 or _looks_like_holder_noise(hn):
        return None
    return hn


def _looks_like_holder_noise(s: str) -> bool:
    su = s.upper().strip()
    if su in {"NOT", "N/A", "NONE"}:
        return True
    if "SHOULD ANY OF THE ABOVE" in su:
        return True
    return False


def description_of_operations(text: str) -> Optional[str]:
    m = re.search(
        r"DESCRIPTION\s+OF\s+OPERATIONS[^\n]*\n(.+?)(?=\n\s*CERTIFICATE\s+HOLDER\b)",
        text,
        re.I | re.DOTALL,
    )
    if not m:
        return None
    blob = m.group(1).strip()
    blob = re.sub(r"[ \t]+\n", "\n", blob)
    blob = re.sub(r"\n{3,}", "\n\n", blob)
    return blob if len(blob) > 50 else None


def insurer_lines(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in re.finditer(
        r"^INSURER\s*([A-F])\s*:\s*(.+?)\s+(\d{5})\s*$",
        text,
        re.I | re.MULTILINE,
    ):
        out.append({"letter": m.group(1).upper(), "name": m.group(2).strip(), "naic": m.group(3)})
    return out


def coverage_policy_rows(text: str) -> list[dict[str, Any]]:
    """
    Lines like: GL 7821-04-53920 04/01/2026 04/01/2027
    """
    rows: list[dict[str, Any]] = []
    lob = {"GL": "GL", "CA": "AUTO", "UMB": "UMB", "WC": "WC", "BR": "PROPERTY"}
    for m in re.finditer(
        r"\b(GL|CA|UMB|WC|BR)\s+([\d\-]+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.I,
    ):
        code = m.group(1).upper()
        rows.append(
            {
                "line_of_business": lob.get(code, code),
                "policy_number": m.group(2).strip(),
                "effective_date": m.group(3),
                "expiration_date": m.group(4),
            }
        )
    return rows


def parse_mmddyyyy(s: str) -> Optional[date]:
    s = (s or "").strip()
    try:
        from datetime import datetime

        return datetime.strptime(s, "%m/%d/%Y").date()
    except Exception:
        return None


def cancellation_days(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})\s*[-\u2013]?\s*Day\s+notice\s+of\s+cancellation", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None
