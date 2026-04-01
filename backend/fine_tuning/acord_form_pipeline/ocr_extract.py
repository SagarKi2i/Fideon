from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pdfplumber

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pytesseract
    from PIL import Image
    import io
except Exception:
    pytesseract = None
    Image = None


def _text_pdfplumber(pdf_path: Path, max_pages: int) -> str:
    pages: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages[:max_pages]:
            pages.append((page.extract_text() or "").strip())
    return "\n\n".join([p for p in pages if p]).strip()


def _text_pymupdf(pdf_path: Path, max_pages: int) -> str:
    if fitz is None:
        return ""
    doc = fitz.open(str(pdf_path))
    try:
        pages: List[str] = []
        for i in range(min(len(doc), max_pages)):
            pages.append((doc.load_page(i).get_text("text") or "").strip())
        return "\n\n".join([p for p in pages if p]).strip()
    finally:
        doc.close()


def _text_tesseract(pdf_path: Path, max_pages: int, dpi: int = 200) -> str:
    if fitz is None or pytesseract is None or Image is None:
        return ""
    doc = fitz.open(str(pdf_path))
    pages: List[str] = []
    try:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(min(len(doc), max_pages)):
            pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages.append((pytesseract.image_to_string(img) or "").strip())
    finally:
        doc.close()
    return "\n\n".join([p for p in pages if p]).strip()


def extract_ocr_text(pdf_path: Path, max_pages: int = 10) -> Dict[str, str]:
    """
    Layout-aware first; OCR fallback if text is too sparse.
    """
    text = _text_pdfplumber(pdf_path, max_pages=max_pages)
    engine = "pdfplumber"

    if len(text) < 200:
        alt = _text_pymupdf(pdf_path, max_pages=max_pages)
        if len(alt) > len(text):
            text = alt
            engine = "pymupdf"

    if len(text) < 200:
        ocr = _text_tesseract(pdf_path, max_pages=max_pages)
        if len(ocr) > len(text):
            text = ocr
            engine = "tesseract_ocr"

    ocr_confidence = _estimate_text_quality(text)
    template = detect_template(text)
    return {
        "text": text,
        "engine": engine,
        "ocr_confidence": f"{ocr_confidence:.3f}",
        "template": template,
    }


def _estimate_text_quality(text: str) -> float:
    src = text or ""
    if not src.strip():
        return 0.0
    total = len(src)
    alnum = sum(1 for ch in src if ch.isalnum())
    lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
    avg_line_len = sum(len(ln) for ln in lines) / max(len(lines), 1)
    score = 0.5 * (alnum / max(total, 1)) + 0.5 * min(avg_line_len / 80.0, 1.0)
    return float(max(0.0, min(score, 1.0)))


def detect_template(text: str) -> str:
    src = (text or "").upper()
    if "ACORD 125" in src or "COMMERCIAL INSURANCE APPLICATION" in src:
        return "acord_125"
    return "unknown"


def run_batch(input_dir: Path, out_dir: Path, max_pages: int = 10, min_ocr_confidence: float = 0.7) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta: List[Dict[str, str]] = []
    for pdf_path in sorted(input_dir.glob("*.pdf")):
        result = extract_ocr_text(pdf_path, max_pages=max_pages)
        txt_path = out_dir / f"{pdf_path.stem}.txt"
        if float(result["ocr_confidence"]) >= min_ocr_confidence:
            txt_path.write_text(result["text"], encoding="utf-8")
        else:
            txt_path.write_text("", encoding="utf-8")
        meta.append(
            {
                "file": pdf_path.name,
                "text_file": txt_path.name,
                "engine": result["engine"],
                "chars": str(len(result["text"])),
                "ocr_confidence": result["ocr_confidence"],
                "template": result["template"],
                "status": "ok" if float(result["ocr_confidence"]) >= min_ocr_confidence else "bad_input",
            }
        )
    (out_dir / "ocr_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR extract ACORD PDFs to raw text files.")
    parser.add_argument("--input-dir", required=True, help="Directory containing ACORD PDFs")
    parser.add_argument("--out-dir", required=True, help="Directory to write OCR .txt files")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--min-ocr-confidence", type=float, default=0.7)
    args = parser.parse_args()
    run_batch(
        Path(args.input_dir),
        Path(args.out_dir),
        max_pages=args.max_pages,
        min_ocr_confidence=args.min_ocr_confidence,
    )


if __name__ == "__main__":
    main()

