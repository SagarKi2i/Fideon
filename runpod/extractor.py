"""
Full ACORD extraction pipeline for RunPod.

Pipeline:
  [Parallel] Arm A: Surya OCR  (layout + line OCR → ocr_text, surya_fields)
             Arm B: Docling     (structure + tables + KV → markdown, tables, kv_pairs)
  [Serial]   Qwen2-VL          (original images + both arm outputs → fields JSON, raw text, markdown)

Models are loaded lazily and cached for reuse across requests.
"""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Surya OCR singletons (0.6.x API) ─────────────────────────────────────────
_surya_lock = threading.Lock()
_det_predictor = None
_rec_predictor = None
_surya_loaded = False

# ── Docling singleton ─────────────────────────────────────────────────────────
_docling_lock = threading.Lock()
_docling_converter = None
_docling_loaded = False

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


def _load_docling() -> None:
    global _docling_converter, _docling_loaded
    with _docling_lock:
        if _docling_loaded:
            return
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True           # needed for scanned PDFs
        pipeline_options.do_table_structure = True

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        _docling_loaded = True


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


# ── Arm A: Surya OCR ──────────────────────────────────────────────────────────

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


# ── Arm B: Docling ────────────────────────────────────────────────────────────

def _run_docling(pdf_path: str) -> Dict[str, Any]:
    """Run Docling on the PDF; returns markdown, tables list, and KV pairs dict."""
    _load_docling()
    try:
        result = _docling_converter.convert(pdf_path)
        doc = result.document

        markdown = doc.export_to_markdown()

        # Export each detected table to markdown (pandas not required)
        tables: List[str] = []
        for table in getattr(doc, "tables", []):
            try:
                tables.append(table.export_to_markdown())
            except Exception:
                pass

        # Extract KV pairs when Docling's layout parser detects them
        kv_pairs: Dict[str, str] = {}
        for item in getattr(doc, "key_value_items", []):
            try:
                key = (item.key.text or "").strip()
                val = (item.value.text or "").strip()
                if key:
                    kv_pairs[key] = val
            except Exception:
                pass

        return {"markdown": markdown, "tables": tables, "kv_pairs": kv_pairs}
    except Exception as exc:
        return {"markdown": "", "tables": [], "kv_pairs": {}, "error": str(exc)}


# ── Output parser ─────────────────────────────────────────────────────────────

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


def _parse_qwen_output(text: str) -> Tuple[Optional[Dict], str, str]:
    """
    Parse Qwen output for FIELDS: / RAW TEXT: / MARKDOWN: sections.
    Returns (fields_dict, raw_text, markdown).
    """
    fields_marker = "FIELDS:"
    raw_marker = "RAW TEXT:"
    md_marker = "MARKDOWN:"

    fi = text.find(fields_marker)
    ri = text.find(raw_marker)
    mi = text.find(md_marker)

    # FIELDS block ends at whichever marker comes next
    if fi != -1:
        next_after_fields = min(
            (x for x in (ri, mi) if x != -1 and x > fi),
            default=len(text),
        )
        parsed = _parse_fields_section(text[fi + len(fields_marker) : next_after_fields])
    else:
        parsed = _parse_fields_section(text)

    # RAW TEXT block ends at MARKDOWN: (if present after it)
    if ri != -1:
        raw_end = mi if (mi != -1 and mi > ri) else len(text)
        raw_text = text[ri + len(raw_marker) : raw_end].strip()
    else:
        raw_text = ""

    qwen_markdown = text[mi + len(md_marker) :].strip() if mi != -1 else ""

    return parsed, raw_text, qwen_markdown


# ── Qwen2-VL prompt ───────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are an expert insurance document parser. You are given page images of an ACORD form,
plus pre-processed outputs from two independent parsers (Surya OCR and Docling).

Use ALL inputs — the images (ground truth), Surya OCR text, Docling markdown, and Docling KV pairs —
to produce three outputs:

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
<full verbatim text extracted from the form, line by line, preserving reading order top-to-bottom>

MARKDOWN:
<clean markdown of the entire document — preserve tables as markdown tables, use ## for section headers>
---

Checkbox Rules (IMPORTANT):
- Checked if it contains a tick (✓), X, cross (×), filled square (■), filled circle (●), or any handwritten mark.
- Unchecked only if the box is completely empty.
- Represent as: true (checked) / false (unchecked).
- Treat X marks and tick marks equally as "checked".

Additional Rules:
- If a field label is visible but the value is empty or illegible, include the key with "".
- Do not skip any field, checkbox, or section header.
- For tables (coverage schedules, vehicle lists, etc.), represent each row as a nested object in an array.
- When Docling and Surya disagree on a value, prefer what you can verify directly in the image.
- Output valid JSON in the FIELDS section. No commentary — only the three structured sections above.
"""


# ── Qwen2-VL inference ────────────────────────────────────────────────────────

def _run_qwen_extraction(
    images: List,
    surya_ocr_text: str,
    docling_result: Dict[str, Any],
    form_type: str,
) -> Dict[str, Any]:
    _load_qwen()
    import torch

    page_images = images[:2]

    # Build reference context from both arms
    context_parts: List[str] = []
    if surya_ocr_text.strip():
        context_parts.append(
            f"=== Surya OCR text (line-by-line) ===\n{surya_ocr_text[:2500]}"
        )
    if docling_result.get("markdown", "").strip():
        context_parts.append(
            f"=== Docling structured markdown (tables + layout) ===\n{docling_result['markdown'][:2500]}"
        )
    if docling_result.get("kv_pairs"):
        kv_str = "\n".join(f"{k}: {v}" for k, v in list(docling_result["kv_pairs"].items())[:60])
        context_parts.append(f"=== Docling KV pairs ===\n{kv_str}")
    if docling_result.get("tables"):
        tables_str = "\n\n".join(docling_result["tables"][:5])
        context_parts.append(f"=== Docling extracted tables ===\n{tables_str[:1500]}")

    prompt = _PROMPT_TEMPLATE
    if context_parts:
        prompt += "\n\n" + "\n\n".join(context_parts)

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

    parsed, qwen_raw_text, qwen_markdown = _parse_qwen_output(output_text)
    fields = parsed if parsed is not None else {"_raw_qwen_output": output_text}
    return {"fields": fields, "qwen_raw_text": qwen_raw_text, "qwen_markdown": qwen_markdown}


# ── Public entry point ────────────────────────────────────────────────────────

def run_full_extraction(pdf_path: str, form_type: str = "25") -> Dict[str, Any]:
    """
    Full ACORD extraction pipeline.

    Step 1 (parallel): Surya OCR + Docling run concurrently on separate threads.
    Step 2 (serial):   Qwen2-VL receives page images + both arm outputs.

    Returns: { form_type_detected, pdf_type, extracted_json, full_text, markdown }
    """
    if not Path(pdf_path).exists():
        return {"error": f"File not found: {pdf_path}"}

    images = _pdf_to_images(pdf_path)
    if not images:
        return {"error": "No pages found in PDF"}

    # Detect digital vs scanned
    import fitz as _fitz
    _doc = _fitz.open(pdf_path)
    _embedded = "".join(p.get_text("text") for p in _doc).strip()
    _doc.close()
    pdf_type = "digital" if len(_embedded) > 100 else "scanned"

    # ── Step 1: Surya + Docling in parallel ───────────────────────────────────
    surya_ocr_text: str = ""
    docling_result: Dict[str, Any] = {"markdown": "", "tables": [], "kv_pairs": {}}

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_surya = pool.submit(_run_surya_ocr, images)
        future_docling = pool.submit(_run_docling, pdf_path)

        for future in as_completed([future_surya, future_docling]):
            if future is future_surya:
                surya_ocr_text = future.result()
            else:
                docling_result = future.result()

    # ── Step 2: Qwen2-VL with both arm outputs ────────────────────────────────
    qwen_result = _run_qwen_extraction(images, surya_ocr_text, docling_result, form_type)

    return {
        "form_type_detected": f"acord{form_type}",
        "pdf_type": pdf_type,
        "extracted_json": qwen_result["fields"],
        "full_text": qwen_result["qwen_raw_text"] or surya_ocr_text,
        "markdown": qwen_result["qwen_markdown"] or docling_result.get("markdown", ""),
    }
