"""
Full ACORD extraction pipeline for RunPod.
Pipeline: Surya OCR 0.17.x (DetectionPredictor + RecognitionPredictor) → Qwen2-VL field extraction.
Models are loaded lazily and cached for reuse across requests.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Surya OCR singletons (0.17.x class-based API) ────────────────────────────
_surya_lock = threading.Lock()
_det_predictor = None
_rec_predictor = None
_surya_loaded = False

# ── Qwen2-VL singletons ───────────────────────────────────────────────────────
_qwen_lock = threading.Lock()
_qwen_model = None
_qwen_processor = None
_qwen_loaded = False

QWEN_MODEL_ID = os.getenv("QWEN_MODEL_ID", "/workspace/models/qwen2-vl-7b")


# ── Model loaders ─────────────────────────────────────────────────────────────

def _load_surya() -> None:
    global _det_predictor, _rec_predictor, _surya_loaded
    with _surya_lock:
        if _surya_loaded:
            return
        from surya.detection import DetectionPredictor
        from surya.recognition import FoundationPredictor, RecognitionPredictor

        _det_predictor = DetectionPredictor()
        _rec_predictor = RecognitionPredictor(
            foundation_predictor=FoundationPredictor()
        )
        _surya_loaded = True


def _load_qwen() -> None:
    global _qwen_model, _qwen_processor, _qwen_loaded
    with _qwen_lock:
        if _qwen_loaded:
            return
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

        _qwen_processor = AutoProcessor.from_pretrained(QWEN_MODEL_ID)
        _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            QWEN_MODEL_ID,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
        )
        _qwen_model.eval()
        _qwen_loaded = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pdf_to_images(pdf_path: str, dpi: int = 150) -> List:
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


def _run_surya_ocr(images: List) -> str:
    _load_surya()
    ocr_results = _rec_predictor(images, det_predictor=_det_predictor)

    lines: List[str] = []
    for result in ocr_results:
        for tl in result.text_lines:
            text = (tl.text or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _parse_fields_section(section: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a FIELDS: section, stripping optional code fences."""
    stripped = section.strip()
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        last_fence = stripped.rfind("```")
        if first_nl != -1 and last_fence > first_nl:
            stripped = stripped[first_nl + 1 : last_fence].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _parse_qwen_output(text: str) -> tuple:
    """
    Parse Qwen output that may contain FIELDS: / RAW TEXT: sections.
    Returns (fields_dict, raw_text_str).
    """
    fields_marker = "FIELDS:"
    raw_marker = "RAW TEXT:"

    fi = text.find(fields_marker)
    ri = text.find(raw_marker)

    if fi != -1:
        fields_block = text[fi + len(fields_marker):]
        if ri != -1 and ri > fi:
            fields_block = text[fi + len(fields_marker) : ri]
        parsed = _parse_fields_section(fields_block)
    else:
        # Fallback: try to parse the whole text as JSON
        parsed = _parse_fields_section(text)

    raw_text = text[ri + len(raw_marker):].strip() if ri != -1 else ""

    return parsed, raw_text


_PROMPT_TEMPLATE = """\
You are an expert insurance document parser. You are given an image of an ACORD form.

Your task is to:

1. Extract ALL visible fields and their values as structured key-value pairs.
2. Also return the complete raw text content of the form, preserving reading order (top to bottom, left to right).

Follow this exact output format:

---
FIELDS:
{{
  "Agency": "...",
  "Agency Customer ID": "...",
  "Date": "...",
  "Insured Name": "...",
  "Mailing Address": "...",
  "City": "...",
  "State": "...",
  "ZIP Code": "...",
  "Phone": "...",
  "Policy Number": "...",
  "Effective Date": "...",
  "Expiration Date": "...",
  "Company": "...",
  "Coverage Type": "...",
  "Premium": "...",
  ... (include ALL other fields visible on the form, even if blank — use "" for empty fields)
}}

RAW TEXT:
<full verbatim text extracted from the form, line by line, preserving layout>
---

Checkbox Rules (IMPORTANT):
- A checkbox is considered CHECKED if it contains ANY of the following marks:
    - A tick or checkmark (✓ or √)
    - An X mark or cross (X or ×)
    - A filled square or circle (■, ●)
    - Any handwritten mark inside the box
- A checkbox is UNCHECKED only if the box is completely empty.
- Represent checkbox state as:
    - true  → if checked by ANY mark (tick, X, cross, fill, etc.)
    - false → if completely empty
- Do NOT assume a mark type — treat X marks and tick marks equally as "checked".

Additional Rules:
- If a field label is visible but the value is empty or illegible, include the key with an empty string value.
- Do not skip any field, checkbox, or section header.
- For tables (e.g., coverage schedules, vehicle lists), represent each row as a nested object inside an array under the appropriate key.
- Output valid JSON for the FIELDS section.
- Do not add commentary or explanation — only the structured output above.
"""


def _run_qwen_extraction(images: List, ocr_text: str, form_type: str) -> Dict[str, Any]:
    _load_qwen()
    import torch

    page_images = images[:2]

    prompt = _PROMPT_TEMPLATE
    if ocr_text.strip():
        prompt += f"\n\nSurya OCR reference text (use to assist field identification):\n{ocr_text[:3000]}"

    content: List[Dict[str, Any]] = [
        {"type": "image", "image": img} for img in page_images
    ]
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    text_input = _qwen_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    image_inputs = [
        item["image"]
        for msg in messages
        if isinstance(msg.get("content"), list)
        for item in msg["content"]
        if item.get("type") == "image"
    ]

    inputs = _qwen_processor(
        text=[text_input],
        images=image_inputs if image_inputs else None,
        padding=True,
        return_tensors="pt",
    )

    device = next(_qwen_model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = _qwen_model.generate(**inputs, max_new_tokens=3072)

    trimmed = [out[len(inp):] for inp, out in zip(inputs["input_ids"], generated_ids)]
    output_text = _qwen_processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    parsed, qwen_raw_text = _parse_qwen_output(output_text)
    fields = parsed if parsed is not None else {"_raw_qwen_output": output_text}
    return {"fields": fields, "qwen_raw_text": qwen_raw_text}


# ── Public entry point ────────────────────────────────────────────────────────

def run_full_extraction(pdf_path: str, form_type: str = "25") -> Dict[str, Any]:
    """
    Full ACORD extraction pipeline.
    Returns: { form_type_detected, pdf_type, extracted_json, full_text }
    """
    if not Path(pdf_path).exists():
        return {"error": f"File not found: {pdf_path}"}

    images = _pdf_to_images(pdf_path)
    if not images:
        return {"error": "No pages found in PDF"}

    ocr_text = _run_surya_ocr(images)

    # Detect via PyMuPDF: digital PDFs have embedded text; scanned ones don't
    import fitz as _fitz
    _doc = _fitz.open(pdf_path)
    _embedded = "".join(p.get_text("text") for p in _doc).strip()
    _doc.close()
    pdf_type = "digital" if len(_embedded) > 100 else "scanned"

    qwen_result = _run_qwen_extraction(images, ocr_text, form_type)

    return {
        "form_type_detected": f"acord{form_type}",
        "pdf_type": pdf_type,
        "extracted_json": qwen_result["fields"],
        "full_text": qwen_result["qwen_raw_text"] or ocr_text,
    }
