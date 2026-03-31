"""
Conservative ACORD 125 (Commercial Insurance Application) text heuristics.

ACORD 125 layout varies by carrier and edition; this is not as stable as ACORD 25's two-column header.
Use when: fillable AcroForm + VL/LLM are primary; these rules only patch missing/suspicious producer & insured names.

Tune against real PDFs in fine_tuning/Sample Data/ when you add Acord-125-sample*.pdf.
"""

from __future__ import annotations

import re
from typing import Optional


def is_acord125_text(text: str) -> bool:
    u = (text or "").upper()
    if "ACORD 125" in u or "ACORD125" in u.replace(" ", ""):
        return True
    if "COMMERCIAL INSURANCE APPLICATION" in u and "ACORD" in u:
        return True
    return False


def agency_first_line(text: str) -> Optional[str]:
    """First substantive line after an AGENCY / PRODUCER header (common page-1 layout)."""
    m = re.search(
        r"(?:^|\n)\s*AGENCY\s*(?:CUSTOMER|\#|NUMBER)?\s*\n\s*([^\n]+)",
        text,
        re.I | re.MULTILINE,
    )
    if m:
        line = m.group(1).strip()
        if _looks_like_name_line(line):
            return line
    m = re.search(
        r"(?:^|\n)\s*PRODUCER(?:\s+INFORMATION)?\s*\n\s*([^\n]+)",
        text,
        re.I | re.MULTILINE,
    )
    if m:
        line = m.group(1).strip()
        if _looks_like_name_line(line):
            return line
    return None


def first_named_insured_line(text: str) -> Optional[str]:
    """
    First line under NAMED INSURED / FIRST NAMED INSURED blocks (not ACORD 25 certificate layout).
    """
    for pat in (
        r"FIRST\s+NAMED\s+INSURED[^\n]*\n\s*([^\n]+)",
        r"NAMED\s+INSURED\s+AND\s+MAILING\s+ADDRESS[^\n]*\n\s*([^\n]+)",
        r"NAMED\s+INSURED\s*\(SN\d*\)[^\n]*\n\s*([^\n]+)",
    ):
        m = re.search(pat, text, re.I | re.MULTILINE)
        if m:
            line = m.group(1).strip()
            if _looks_like_name_line(line):
                return line
    return None


def _looks_like_name_line(s: str) -> bool:
    t = (s or "").strip()
    if len(t) < 4 or len(t) > 200:
        return False
    u = t.upper()
    bad = (
        "SEE ATTACHED",
        "CONTINUED",
        "PAGE",
        "MM/DD/YYYY",
        "PROPOSED EFF",
        "NAIC",
        "UNDERWRITER",
    )
    if any(b in u for b in bad):
        return False
    if re.match(r"^\d+[\s./-]+\d+", t):
        return False
    return True
