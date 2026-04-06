from __future__ import annotations

import re
from typing import Dict


_LABEL_NORMALIZATIONS: Dict[str, str] = {
    r"\bAGENCY\b\s*:?\s*": "Agency Name: ",
    r"\bAGENCY NAME\b\s*:?\s*": "Agency Name: ",
    r"\bCONTACT\b\s*:?\s*": "Contact Name: ",
    r"\bCARRIER\b\s*:?\s*": "Carrier: ",
    r"\bPOLICY\s*#?\b\s*:?\s*": "Policy Number: ",
    r"\bEMAIL\b\s*:?\s*": "Email: ",
    r"\bPHONE\b\s*:?\s*": "Phone: ",
}


def _normalize_phone(text: str) -> str:
    # Standardize obvious US-like numbers into (xxx) xxx-xxxx where possible.
    def repl(m: re.Match[str]) -> str:
        d = re.sub(r"\D", "", m.group(0))
        if len(d) == 10:
            return f"({d[0:3]}) {d[3:6]}-{d[6:10]}"
        return m.group(0)

    return re.sub(r"(?:\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}", repl, text)


def _normalize_email(text: str) -> str:
    # Lowercase valid email tokens only.
    def repl(m: re.Match[str]) -> str:
        return m.group(0).lower()

    return re.sub(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", repl, text)


def _normalize_dates(text: str) -> str:
    # Keep date-like tokens but normalize separators to slash.
    return re.sub(r"\b(\d{1,2})[\-\.](\d{1,2})[\-\.](\d{2,4})\b", r"\1/\2/\3", text)


def structure_text(raw_text: str) -> str:
    """
    Build a stable key-value representation from noisy OCR text so the model
    sees consistent structure during training.
    """
    patterns = {
        "Agency Name": r"\bAGENCY(?: NAME)?\b[:\s]*(.+)",
        "Contact Name": r"\bCONTACT(?: NAME)?\b[:\s]*(.+)",
        "Carrier": r"\bCARRIER\b[:\s]*(.+)",
        "Policy Number": r"\bPOLICY(?: NUMBER| #)?\b[:\s]*(.+)",
        "Email": r"\bEMAIL\b[:\s]*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
        "Phone": r"\bPHONE\b[:\s]*(.+)",
    }
    structured = []
    for key, pattern in patterns.items():
        m = re.search(pattern, raw_text, flags=re.IGNORECASE)
        value = m.group(1).strip() if m and m.group(1).strip() else "null"
        structured.append(f"{key}: {value}")
    return "\n".join(structured)


def _prune_noisy_sections(text: str) -> str:
    """
    Keep high-signal ACORD regions and drop known noisy sections.
    """
    drop_patterns = [
        r"(?is)attachments?.*?(?=\n[A-Z][^\n]{0,50}:|\Z)",
        r"(?is)loss\s+history.*?(?=\n[A-Z][^\n]{0,50}:|\Z)",
        r"(?is)legal\s+notice.*?(?=\n[A-Z][^\n]{0,50}:|\Z)",
        r"(?is)fraud\s+warning.*?(?=\n[A-Z][^\n]{0,50}:|\Z)",
    ]
    out = text
    for p in drop_patterns:
        out = re.sub(p, " ", out)
    return re.sub(r"\n{3,}", "\n\n", out)


def clean_ocr_text(raw_text: str) -> str:
    text = raw_text or ""
    # Remove high-noise artifacts.
    text = text.replace("[object Object]", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    # Merge line-broken labels where possible.
    text = re.sub(r":\s*\n\s*", ": ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    for pattern, replacement in _LABEL_NORMALIZATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = _normalize_phone(text)
    text = _normalize_email(text)
    text = _normalize_dates(text)
    text = _prune_noisy_sections(text)

    # Remove leftover noisy blank lines.
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    cleaned = "\n".join(lines).strip()
    structured = structure_text(cleaned)
    return f"{cleaned}\n\n[Structured Fields]\n{structured}".strip()


def before_after_example() -> Dict[str, str]:
    before = "AGENCY:\nConvenis Agency  \nPHONE: 630.555.0244 \n[object Object]"
    after = clean_ocr_text(before)
    return {"before": before, "after": after}

