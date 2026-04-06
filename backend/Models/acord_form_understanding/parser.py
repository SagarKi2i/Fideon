"""
ACORD form understanding utilities.

This module provides light‑weight, text‑based parsing utilities that work on
pre‑extracted ACORD form text (e.g. from OCR or PDF‑to‑text). It focuses on
industry‑standard forms like ACORD 25, 27, 80, 85, 90, 125, 126, 140.

The goal is to normalize key entities:
- producer (agency)
- insured
- holder / certificate holder
- policy coverages (per line of business)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from .schemas import (
    AcordCarrier,
    AcordFormSummary,
    AcordInsured,
    AcordPolicyCoverage,
    AcordProducer,
    ExtractionMeta,
)


_FORM_ID_PATTERN = re.compile(r"ACORD\s+(\d+)", re.IGNORECASE)
_PRODUCER_LABEL = re.compile(r"\bPRODUCER\b", re.IGNORECASE)
_INSURED_LABEL = re.compile(r"\bINSURED\b", re.IGNORECASE)

_GENERIC_SECTION_LABEL = re.compile(r"^[A-Z][A-Z\s/&'-]{3,}$")


def detect_form_type(text: str) -> Optional[str]:
    """
    Detect the ACORD form identifier from free text, e.g. 'ACORD 25'.
    """
    match = _FORM_ID_PATTERN.search(text)
    if not match:
        return None
    return f"ACORD {match.group(1)}"


def _extract_first_line_matching(pattern: re.Pattern[str], text: str) -> Optional[str]:
    for line in text.splitlines():
        if pattern.search(line):
            return line.strip()
    return None


def _extract_block_after_label(
    label_pattern: re.Pattern[str],
    text: str,
    *,
    max_lines: int = 4,
) -> tuple[Optional[str], float]:
    """
    Robust extraction for ACORD blocks where values are often on the next line(s).

    Returns: (value, confidence)
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    for i, raw in enumerate(lines):
        if not label_pattern.search(raw or ""):
            continue
        line = raw.strip()

        # 1) Same-line value: "PRODUCER: XYZ"
        parts = re.split(label_pattern, line, maxsplit=1)
        if len(parts) == 2:
            tail = parts[1].strip(" :-\t")
            if tail:
                return tail, 0.95

        # 2) Next non-empty lines: typical layout is label on its own line
        collected: list[str] = []
        for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
            candidate = (lines[j] or "").strip()
            if not candidate:
                continue
            # Stop if we hit another section label
            if _GENERIC_SECTION_LABEL.match(candidate) and len(collected) > 0:
                break
            # Avoid picking up the next label itself
            if label_pattern.search(candidate):
                continue
            collected.append(candidate)
            # Name is usually first useful line; break early once we have something.
            if collected:
                break

        if collected:
            return collected[0], 0.85
        return None, 0.0
    return None, 0.0


def _parse_producer(text: str) -> AcordProducer:
    """
    Heuristic producer parsing based on typical ACORD layouts.
    """
    name, confidence = _extract_block_after_label(_PRODUCER_LABEL, text)
    return AcordProducer(name=name, name_confidence=confidence)


def _parse_insured(text: str) -> AcordInsured:
    """
    Heuristic insured parsing based on 'INSURED' label.
    """
    name, confidence = _extract_block_after_label(_INSURED_LABEL, text)
    return AcordInsured(name=name, name_confidence=confidence)


def _parse_policy_blocks(text: str) -> list[AcordPolicyCoverage]:
    """
    Very small, heuristic parser for policy coverages.

    It looks for patterns like:
    - 'COMMERCIAL GENERAL LIABILITY'
    - 'AUTOMOBILE LIABILITY'
    - 'UMBRELLA / EXCESS LIABILITY'
    - 'WORKERS COMPENSATION'
    and then tries to find a policy number and effective/expiration dates
    nearby in the text.
    """
    coverages: list[AcordPolicyCoverage] = []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)

    coverage_labels = {
        "GL": re.compile(r"COMMERCIAL\s+GENERAL\s+LIABILITY", re.IGNORECASE),
        "AUTO": re.compile(r"AUTOMOBILE\s+LIABILITY", re.IGNORECASE),
        "UMB": re.compile(r"(UMBRELLA|EXCESS)\s+LIABILITY", re.IGNORECASE),
        "WC": re.compile(r"WORKERS[’']?\s+COMPENSATION", re.IGNORECASE),
        "PROPERTY": re.compile(r"PROPERTY\s+COVERAGE", re.IGNORECASE),
    }

    date_pattern = re.compile(
        r"(\d{2}[/-]\d{2}[/-]\d{2,4})", re.IGNORECASE
    )  # 01/01/2025 etc.
    policy_pattern = re.compile(r"\bPOLICY\s*NUMBER\b[:#]?\s*(\S+)", re.IGNORECASE)
    naic_pattern = re.compile(r"\bNAIC\s*#\b\s*(\S+)", re.IGNORECASE)

    for lob, pattern in coverage_labels.items():
        m = pattern.search(joined)
        if not m:
            continue

        # Search within a wider window around the match for dates/policy number.
        # ACORD often places policy # and dates on nearby lines, not necessarily the same line.
        hit_line_idx = joined[: m.start()].count("\n")
        win_start = max(0, hit_line_idx - 8)
        win_end = min(len(lines), hit_line_idx + 12)
        window = "\n".join(lines[win_start:win_end])

        pol_match = policy_pattern.search(window)
        dates = date_pattern.findall(window)
        naic_match = naic_pattern.search(window)

        effective = _parse_date(dates[0]) if dates else None
        expiration = _parse_date(dates[1]) if len(dates) > 1 else None

        coverage = AcordPolicyCoverage(
            line_of_business=lob,
            block_confidence=0.85,
            policy_number=pol_match.group(1) if pol_match else None,
            policy_number_confidence=0.9 if pol_match else 0.0,
            effective_date=effective,
            effective_date_confidence=0.85 if effective else 0.0,
            expiration_date=expiration,
            expiration_date_confidence=0.85 if expiration else 0.0,
        )
        if naic_match:
            coverage.insurers.append(AcordCarrier(naic_number=naic_match.group(1)))

        coverages.append(coverage)

    return coverages


def _parse_date(value: str) -> Optional[datetime.date]:
    value = value.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_acord_form(text: str) -> AcordFormSummary:
    """
    Parse ACORD form text into a normalized summary object.

    This is intentionally conservative: if a field cannot be confidently
    identified, it is left as None instead of guessed.
    """
    form_type = detect_form_type(text)

    producer = _parse_producer(text)
    insured = _parse_insured(text)
    coverages = _parse_policy_blocks(text)

    confidence_values: list[float] = []
    if producer and producer.name_confidence is not None:
        confidence_values.append(float(producer.name_confidence))
    if insured and insured.name_confidence is not None:
        confidence_values.append(float(insured.name_confidence))
    for c in coverages:
        for v in [
            c.block_confidence,
            c.policy_number_confidence,
            c.effective_date_confidence,
            c.expiration_date_confidence,
        ]:
            if v is not None:
                confidence_values.append(float(v))
    overall = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0

    summary = AcordFormSummary(
        form_type=form_type,
        producer=producer,
        insured=insured,
        coverages=coverages,
        overall_confidence=overall,
        raw_text=text,
        extraction_meta=ExtractionMeta(
            structured_response_source="Fallback response",
            extraction_engine="legacy_heuristic",
        ),
    )
    return summary

