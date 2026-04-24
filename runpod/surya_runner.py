"""
Surya OCR runner for RunPod (surya-ocr 0.17.x class-based API).
Models are loaded once on first use and reused for every job.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_lock = threading.Lock()
_det_predictor = None
_rec_predictor = None
_models_loaded = False


def _load_models() -> None:
    global _det_predictor, _rec_predictor, _models_loaded
    with _lock:
        if _models_loaded:
            return
        from surya.detection import DetectionPredictor
        from surya.recognition import FoundationPredictor, RecognitionPredictor

        _det_predictor = DetectionPredictor()
        _rec_predictor = RecognitionPredictor(
            foundation_predictor=FoundationPredictor()
        )
        _models_loaded = True


def _pdf_to_images(pdf_path: str, dpi: int = 150):
    import fitz
    from PIL import Image

    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def _extract_kv_pairs(lines: List[str]) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []
    seen: set = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.{2,60}?)\s*:\s*(.{1,})$", line)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            if key and value and key not in seen:
                seen.add(key)
                pairs.append({"key": key, "value": value})
            continue
        m2 = re.match(r"^(.{2,50}?)\s{2,}(.{1,})$", line)
        if m2:
            key, value = m2.group(1).strip(), m2.group(2).strip()
            if key and value and re.search(r"[A-Za-z]", key) and key not in seen:
                seen.add(key)
                pairs.append({"key": key, "value": value})
    return pairs


def run_surya_on_pdf(
    pdf_path: str,
    langs: Optional[List[str]] = None,
    dpi: int = 150,
) -> Dict[str, Any]:
    if not Path(pdf_path).exists():
        return {"error": f"File not found: {pdf_path}", "total_pages": 0, "pages": [], "fields": [], "full_text": ""}

    _load_models()

    images = _pdf_to_images(pdf_path, dpi=dpi)
    if not images:
        return {"error": "No pages found in PDF", "total_pages": 0, "pages": [], "fields": [], "full_text": ""}

    ocr_results = _rec_predictor(images, det_predictor=_det_predictor)

    pages = []
    all_text_lines: List[str] = []

    for i, result in enumerate(ocr_results):
        lines = []
        for tl in result.text_lines:
            text = (tl.text or "").strip()
            if not text:
                continue
            bbox = getattr(tl, "bbox", None) or [0, 0, 0, 0]
            lines.append({
                "text": text,
                "confidence": round(float(getattr(tl, "confidence", 1.0)), 4),
                "bbox": [round(float(v), 1) for v in bbox],
            })
            all_text_lines.append(text)

        pages.append({"page": i + 1, "line_count": len(lines), "lines": lines})

    fields = _extract_kv_pairs(all_text_lines)

    return {
        "total_pages": len(pages),
        "pages": pages,
        "fields": fields,
        "full_text": "\n".join(all_text_lines),
    }
