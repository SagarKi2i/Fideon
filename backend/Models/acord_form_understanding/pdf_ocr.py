"""
Rasterize PDF pages and OCR text for flattened / scanned-style ACORD PDFs.

- Tesseract (pytesseract): default, lightweight.
- PaddleOCR: optional (pip install paddleocr paddlepaddle); set ACORD_OCR_ENGINE=paddle or auto.

Env:
  ACORD_OCR_ENGINE=auto|tesseract|paddle   (default auto → paddle if importable, else tesseract)
  ACORD_OCR_DPI=200                        (default text-layer PDFs)
  ACORD_FLATTENED_OCR_DPI=300              (no AcroForm — higher DPI for raster OCR)
  ACORD_OCR_MAX_PAGES=20
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Optional

logger = logging.getLogger("fideon.acord.pdf_ocr")

from .ocr_runtime import configure_tesseract_runtime

configure_tesseract_runtime()

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore[assignment]


def _dpi_for_flattened(flattened: bool) -> int:
    if flattened:
        try:
            return max(72, int((os.getenv("ACORD_FLATTENED_OCR_DPI") or "300").strip()))
        except ValueError:
            return 300
    try:
        return max(72, int((os.getenv("ACORD_OCR_DPI") or "200").strip()))
    except ValueError:
        return 200


def _max_pages() -> int:
    try:
        return max(1, int((os.getenv("ACORD_OCR_MAX_PAGES") or "20").strip()))
    except ValueError:
        return 20


def _lines_from_paddle_result(result: object) -> list[str]:
    """Normalize PaddleOCR output across common versions."""
    lines: list[str] = []
    if not result:
        return lines
    for block in result:
        if not block:
            continue
        for item in block:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            txt = item[1]
            if isinstance(txt, (list, tuple)) and len(txt) >= 1:
                lines.append(str(txt[0]).strip())
            elif isinstance(txt, str):
                lines.append(txt.strip())
    return [x for x in lines if x]


_paddle_singleton: object | None = None


def _paddle_ocr_instance():
    global _paddle_singleton
    if _paddle_singleton is False:
        return None
    if _paddle_singleton is not None:
        return _paddle_singleton
    try:
        from paddleocr import PaddleOCR  # type: ignore

        _paddle_singleton = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    except Exception as exc:
        logger.info("PaddleOCR unavailable (%s) — use Tesseract or install paddleocr.", exc)
        _paddle_singleton = False
        return None
    return _paddle_singleton


def _ocr_pages_paddle(pdf_bytes: bytes, *, dpi: int, max_pages: int) -> str:
    if fitz is None or Image is None:
        return ""
    ocr = _paddle_ocr_instance()
    if ocr is None:
        return ""
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not installed — PaddleOCR raster path skipped")
        return ""

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pages_out: list[str] = []
    try:
        n = min(len(doc), max_pages)
        for i in range(n):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
            arr = np.array(img)
            result = ocr.ocr(arr, cls=True)
            lines = _lines_from_paddle_result(result)
            if lines:
                pages_out.append("\n".join(lines))
    finally:
        doc.close()
    return "\n\n".join(pages_out).strip()


def _ocr_pages_tesseract(pdf_bytes: bytes, *, dpi: int, max_pages: int) -> str:
    if fitz is None or Image is None or pytesseract is None:
        return ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    ocr_pages: list[str] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    try:
        n = min(len(doc), max_pages)
        for i in range(n):
            pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
            img = Image.open(BytesIO(pix.tobytes("png")))
            try:
                t = pytesseract.image_to_string(img) or ""
            except Exception as exc:
                logger.warning("Tesseract OCR page %s failed: %s", i, exc)
                t = ""
            if t.strip():
                ocr_pages.append(t)
    finally:
        doc.close()
    return "\n".join(ocr_pages).strip()


def ocr_pdf_pages(
    pdf_bytes: bytes,
    *,
    flattened_pdf: bool = False,
) -> tuple[str, Optional[str]]:
    """
    OCR all pages; return (text, engine_name).

    engine_name is 'paddle', 'tesseract', or None if nothing available.
    """
    if not pdf_bytes or fitz is None:
        return ("", None)
    dpi = _dpi_for_flattened(flattened_pdf)
    max_pages = _max_pages()
    mode = (os.getenv("ACORD_OCR_ENGINE") or "auto").strip().lower()
    if mode not in {"auto", "tesseract", "paddle"}:
        mode = "auto"

    if mode == "tesseract":
        t = _ocr_pages_tesseract(pdf_bytes, dpi=dpi, max_pages=max_pages)
        return (t, "tesseract" if t else None)

    if mode == "paddle":
        p = _ocr_pages_paddle(pdf_bytes, dpi=dpi, max_pages=max_pages)
        if p:
            return (p, "paddle")
        t = _ocr_pages_tesseract(pdf_bytes, dpi=dpi, max_pages=max_pages)
        return (t, "tesseract" if t else None)

    # auto: prefer Paddle when installed and working
    p = _ocr_pages_paddle(pdf_bytes, dpi=dpi, max_pages=max_pages)
    if p:
        return (p, "paddle")
    t = _ocr_pages_tesseract(pdf_bytes, dpi=dpi, max_pages=max_pages)
    return (t, "tesseract" if t else None)
