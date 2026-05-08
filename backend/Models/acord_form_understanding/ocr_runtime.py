"""
Shared Tesseract / tessdata configuration for ACORD PDF OCR (routes + pdf_ocr module).

Call ``configure_tesseract_runtime()`` once at import so staging containers and Windows
dev machines both resolve ``tesseract`` and ``eng.traineddata`` consistently.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("fideon.acord.ocr_runtime")

# backend/ — same as Models/acord_form_understanding → parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def configure_tesseract_runtime() -> None:
    try:
        import pytesseract
    except ImportError:
        return

    # Explicit path wins (staging / Docker / Windows). Interactive shells often have
    # `tesseract` on PATH while Python subprocess does not — shutil.which fixes that.
    resolved: str | None = None
    for candidate in (
        os.getenv("TESSERACT_CMD", "").strip(),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\ProgramData\chocolatey\bin\tesseract.exe",
    ):
        if candidate and Path(candidate).exists():
            resolved = candidate
            break
    if not resolved:
        resolved = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if resolved:
        pytesseract.pytesseract.tesseract_cmd = resolved

    if not (os.getenv("TESSDATA_PREFIX") or "").strip():
        candidates: list[Path] = [
            _BACKEND_ROOT / "tessdata",
            Path("/usr/share/tesseract-ocr/5/tessdata"),
            Path("/usr/share/tesseract-ocr/4.00/tessdata"),
            Path("/usr/share/tesseract-ocr/tessdata"),
            Path("/usr/share/tessdata"),
            Path("/usr/share/tesseract/tessdata"),
        ]
        for prefix in candidates:
            if (prefix / "eng.traineddata").exists():
                os.environ["TESSDATA_PREFIX"] = str(prefix)
                break
    else:
        current = Path(os.getenv("TESSDATA_PREFIX", "").strip())
        if current and not (current / "eng.traineddata").exists():
            candidates = [
                _BACKEND_ROOT / "tessdata",
                Path("/usr/share/tesseract-ocr/5/tessdata"),
                Path("/usr/share/tesseract-ocr/4.00/tessdata"),
                Path("/usr/share/tesseract-ocr/tessdata"),
                Path("/usr/share/tessdata"),
                Path("/usr/share/tesseract/tessdata"),
            ]
            for prefix in candidates:
                if (prefix / "eng.traineddata").exists():
                    os.environ["TESSDATA_PREFIX"] = str(prefix)
                    break

    try:
        v = pytesseract.get_tesseract_version()
        logger.debug("Tesseract OCR available: %s", v)
    except Exception as exc:
        logger.info("Tesseract not callable yet (%s) — flattened PDF OCR may be skipped.", exc)
