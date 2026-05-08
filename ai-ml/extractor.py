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
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("fideon.extractor")


# ── Transformers 4.50+ compatibility patch ────────────────────────────────────
# Must run before any surya or Qwen2-VL imports so the patched symbols are
# available when those packages do their own `from transformers import ...`.
def _patch_transformers_compat() -> None:
    import transformers as _tf
    import transformers.image_utils as _iu

    # surya 0.17.x: `from transformers import PretrainedConfig`
    # Renamed to PreTrainedConfig in 4.50+; restore the old alias.
    if not hasattr(_tf, "PretrainedConfig"):
        _cls = getattr(_tf, "PreTrainedConfig", None)
        if _cls is None:
            try:
                from transformers.configuration_utils import PretrainedConfig as _cls  # type: ignore
            except ImportError:
                from transformers.configuration_utils import PreTrainedConfig as _cls  # type: ignore
        _tf.PretrainedConfig = _cls  # type: ignore[attr-defined]

    # Qwen2-VL processor: `from transformers.image_utils import VideoInput`
    # Moved out of image_utils in 4.50+; inject a compatible type alias.
    if not hasattr(_iu, "VideoInput"):
        from typing import List as _List, Union as _Union
        import numpy as _np
        try:
            from PIL.Image import Image as _PILImage
            _iu.VideoInput = _Union[_List[_PILImage], _List[_np.ndarray]]  # type: ignore[attr-defined]
        except ImportError:
            _iu.VideoInput = list  # type: ignore[attr-defined]


_patch_transformers_compat()

# ── Surya OCR singletons (0.17.x API) ────────────────────────────────────────
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


# ── Fast native extraction for digital PDFs (RunPod-local, no Surya/Qwen) ────
_ACORD_REGEX_PATTERNS: Dict[str, str] = {
    "policy_number": r"(?:Policy(?:\s+No\.?|\s+Number)?)\s*[:\-]\s*([A-Z0-9\-]{4,40})",
    "effective_date": r"(?:Effective|Eff\.?\s*Date)\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    "expiration_date": r"(?:Expiration|Exp(?:iry)?\.?\s*Date)\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    "named_insured": r"(?:NAMED\s+INSURED|Name\s+of\s+Insured)\s*[:\-]?\s*(.{3,80})",
    "mailing_address": r"(?:Mailing\s+Address|Address)\s*[:\-]\s*(.{5,100})",
    "producer_name": r"(?:PRODUCER|Producer|Agency Name)\s*[:\-]\s*(.{3,80})",
    "producer_contact": r"(?:Contact\s+Name|Contact)\s*[:\-]\s*(.{3,60})",
    "producer_phone": r"(?:Phone|Ph\.?)\s*[:\-]\s*([\d\s\(\)\-\+\.]{7,20})",
    "producer_fax": r"(?:Fax)\s*[:\-]\s*([\d\s\(\)\-\+\.]{7,20})",
    "producer_email": r"(?:E-?Mail|Email)\s*[:\-]\s*([\w\.\+\-]+@[\w\.\-]+\.\w{2,})",
    "insurer_a": r"INSURER\s+A\s*[:\-]\s*(.{3,80})",
    "insurer_b": r"INSURER\s+B\s*[:\-]\s*(.{3,80})",
    "insurer_c": r"INSURER\s+C\s*[:\-]\s*(.{3,80})",
    "naic_code": r"NAIC\s*#?\s*[:\-]?\s*(\d{5})",
    "certificate_number": r"(?:Certificate\s+(?:No\.?|Number))\s*[:\-]\s*([A-Z0-9\-]{4,30})",
    "description_of_ops": r"(?:DESCRIPTION\s+OF\s+OPERATIONS)[^\n]*\n(.{10,500})",
    "certificate_holder": r"(?:CERTIFICATE\s+HOLDER)\s*[:\-]?\s*(.{5,200})",
    "gl_each_occurrence": r"(?:Each\s+Occurrence)\s*\$?\s*([\d,]+)",
    "gl_general_aggregate": r"(?:General\s+Aggregate)\s*\$?\s*([\d,]+)",
    "auto_combined_limit": r"(?:Combined\s+Single\s+Limit)\s*\$?\s*([\d,]+)",
    "umbrella_each_occ": r"(?:UMBRELLA|EXCESS).*?Each\s+Occurrence\s*\$?\s*([\d,]+)",
    "wc_el_each_accident": r"E\.L\.\s+Each\s+Accident\s*\$?\s*([\d,]+)",
}


def _extract_kv_from_ocr_text(text: str) -> Dict[str, str]:
    """
    Extract EVERY key-value pair verbatim from Surya OCR text.
    No hardcoded field names. Values taken directly from OCR — zero hallucination.

    Strategy:
      1. Split each line by 3+ whitespace gaps (Surya puts multi-column fields
         side-by-side, e.g. "PHONE: 123   FAX: 456").
      2. For each segment, split at the first colon to get key and value.
      3. Normalise the key to snake_case; keep the value exactly as read.
    """
    kv: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        # Split inline pairs separated by 3+ spaces (multi-column OCR layout)
        segments = re.split(r'\s{3,}', line)
        for seg in segments:
            seg = seg.strip()
            if ":" not in seg:
                continue
            colon_idx = seg.index(":")
            key_raw = seg[:colon_idx].strip()
            value   = seg[colon_idx + 1:].strip()

            if not key_raw or not value:
                continue
            # Reject keys that are too long, too short, or purely numeric/symbolic
            if len(key_raw) < 2 or len(key_raw) > 65:
                continue
            if re.match(r'^[\d\s\-\.\(\)\/\+]+$', key_raw):
                continue
            # Reject separator-only values
            if re.match(r'^[-=_\s]{2,}$', value):
                continue
            value = value[:300]  # cap runaway values
            key = re.sub(r'[^a-z0-9]+', '_', key_raw.lower()).strip('_')
            if key and value and key not in kv:
                kv[key] = value
    return kv


def _extract_digital_native(pdf_path: str, preextracted_text: str = "") -> tuple[Dict[str, Any], str]:
    """Fast digital extraction using local PDF text/widgets/tables + regex (no VLM)."""
    import fitz  # PyMuPDF

    fields: Dict[str, Any] = {}
    raw_text = preextracted_text

    # Layer 1 + 2: PyMuPDF widgets + text
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            for widget in page.widgets() or []:
                name = (widget.field_name or "").strip()
                value = widget.field_value
                if name and value is not None:
                    val = str(value).strip()
                    if val and val not in {"Off", ""}:
                        fields[name] = val
        if not raw_text:
            pages_text = []
            for page in doc:
                text = (page.get_text("text") or "").strip()
                if text:
                    pages_text.append(text)
            raw_text = "\n\n--- Page Break ---\n\n".join(pages_text)
        doc.close()
    except Exception:
        pass

    # Layer 3: pdfplumber tables/KV
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        key = str(row[0] or "").strip().rstrip(":").strip()
                        val = str(row[1] or "").strip()
                        if key and val and not key.isdigit() and key not in fields:
                            fields[key] = val
    except Exception:
        pass

    # Layer 4: regex enrich
    if raw_text:
        for field_key, pattern in _ACORD_REGEX_PATTERNS.items():
            if field_key in fields:
                continue
            m = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
            if not m:
                continue
            value = (m.group(1) or "").strip().split("\n")[0].strip()
            if value:
                fields[field_key] = value

    return fields, raw_text


# ── Model loaders ─────────────────────────────────────────────────────────────

def _load_surya() -> None:
    global _det_predictor, _rec_predictor, _surya_loaded
    with _surya_lock:
        if _surya_loaded:
            return
        import time as _time
        _t0 = _time.time()
        logger.info("[surya] Loading Surya OCR models (DetectionPredictor + RecognitionPredictor)...")
        print("[surya] Loading Surya OCR models...", flush=True)

        from surya.detection import DetectionPredictor
        from surya.recognition import FoundationPredictor, RecognitionPredictor

        _det_predictor = DetectionPredictor()
        _rec_predictor = RecognitionPredictor(
            foundation_predictor=FoundationPredictor()
        )
        _surya_loaded = True
        _elapsed = round(_time.time() - _t0, 1)
        logger.info("[surya] ✓ Surya OCR loaded successfully in %ss", _elapsed)
        print(f"[surya] ✓ Surya OCR loaded successfully in {_elapsed}s", flush=True)


def _load_docling() -> None:
    global _docling_converter, _docling_loaded
    with _docling_lock:
        if _docling_loaded:
            return
        import time as _time
        _t0 = _time.time()
        logger.info("[docling] Loading Docling document converter (OCR + table structure)...")
        print("[docling] Loading Docling document converter...", flush=True)

        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        _docling_loaded = True
        _elapsed = round(_time.time() - _t0, 1)
        logger.info("[docling] ✓ Docling loaded successfully in %ss", _elapsed)
        print(f"[docling] ✓ Docling loaded successfully in {_elapsed}s", flush=True)


def _load_qwen() -> None:
    global _qwen_model, _qwen_processor, _qwen_loaded
    with _qwen_lock:
        if _qwen_loaded:
            return
        import time as _time
        import torch
        from transformers import AutoConfig, AutoProcessor, Qwen2VLForConditionalGeneration

        _t0 = _time.time()
        logger.info("[qwen] Loading Qwen2-VL-7B from %s ...", QWEN_MODEL_ID)
        print(f"[qwen] Loading Qwen2-VL-7B from {QWEN_MODEL_ID} ...", flush=True)

        # Load config first and patch fields missing from older model checkpoints
        # that transformers 4.57 now requires during weight initialisation.
        config = AutoConfig.from_pretrained(QWEN_MODEL_ID)
        if hasattr(config, "vision_config") and not hasattr(config.vision_config, "initializer_range"):
            config.vision_config.initializer_range = 0.02

        logger.info("[qwen] Loading processor...")
        print("[qwen] Loading processor...", flush=True)
        _qwen_processor = AutoProcessor.from_pretrained(QWEN_MODEL_ID)

        # bfloat16 is native on A100 — wider dynamic range, no overflow vs float16.
        # Enable flash_attention_2 when available (requires flash-attn installed);
        # falls back to eager attention transparently if the package is absent.
        _dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        _attn = "flash_attention_2" if torch.cuda.is_available() else None
        try:
            import flash_attn  # noqa: F401 — confirm package is present
        except ImportError:
            _attn = None

        _attn_label = _attn or "eager (flash-attn not installed)"
        logger.info("[qwen] Loading model weights — dtype=%s  attention=%s", _dtype, _attn_label)
        print(f"[qwen] Loading model weights — dtype={_dtype}  attention={_attn_label}", flush=True)

        _load_kwargs: dict = dict(config=config, dtype=_dtype, device_map="auto")
        if _attn:
            _load_kwargs["attn_implementation"] = _attn

        _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            QWEN_MODEL_ID, **_load_kwargs
        )
        _qwen_model.eval()
        _qwen_loaded = True
        _elapsed = round(_time.time() - _t0, 1)
        logger.info("[qwen] ✓ Qwen2-VL-7B loaded successfully in %ss", _elapsed)
        print(f"[qwen] ✓ Qwen2-VL-7B loaded successfully in {_elapsed}s", flush=True)


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
    import traceback as _tb
    _load_surya()
    logger.info("[surya] Running OCR on %d page(s)...", len(images))

    try:
        ocr_results = _rec_predictor(images, det_predictor=_det_predictor)
    except Exception as exc:
        # "index -1 is out of bounds for dimension 0 with size 0" — Surya
        # returns empty detection tensors on blank/sparse pages; the recognition
        # step then crashes trying to slice into an empty result.
        logger.error("[surya] OCR inference failed: %s\n%s", exc, _tb.format_exc())
        raise

    lines: List[str] = []
    for page_idx, result in enumerate(ocr_results):
        page_lines = getattr(result, "text_lines", []) or []
        if not page_lines:
            logger.warning("[surya] Page %d: no text lines detected (blank or very sparse page)", page_idx + 1)
        for tl in page_lines:
            text = (tl.text or "").strip()
            if text:
                lines.append(text)

    logger.info("[surya] OCR complete — %d text lines extracted across %d page(s)", len(lines), len(images))
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
                tables.append(table.export_to_markdown(doc))
            except Exception:
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
        # No FIELDS: marker — try to extract any JSON object from the output
        parsed = _parse_fields_section(text)
        if parsed is None:
            # Last resort: scan for first { ... } block in the entire output
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass

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
You are an expert insurance document parser. You are given page images of an ACORD form.
Pre-processed outputs from Surya OCR and Docling may be appended below when available.

Use ALL available inputs — the images are always the ground truth. If OCR or structured
outputs are not provided, extract all fields directly from the page images.
Produce three outputs:

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

    if not images:
        raise ValueError("_run_qwen_extraction received empty images list — PDF may have no renderable pages")

    # Send up to 4 pages so multi-page ACORD forms (125, 140, etc.) are fully covered
    page_images = images[:4]
    if not surya_ocr_text or not surya_ocr_text.strip():
        surya_ocr_text = "(no OCR text available)"

    # Build reference context from both arms
    context_parts: List[str] = []
    if surya_ocr_text.strip() and surya_ocr_text != "(no OCR text available)":
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
    else:
        prompt += "\n\nNote: Surya OCR and Docling outputs are unavailable. Extract all fields directly from the page images."

    content: List[Dict[str, Any]] = [
        {"type": "image", "image": img} for img in page_images
    ]
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    text_input = _qwen_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # Slow tokenizer (no tokenizer.json in local checkpoint) returns "" for
    # messages that contain image-type content items. Detect and recover by
    # constructing the Qwen2-VL chat text manually. The processor will still
    # expand each single <|image_pad|> to the correct patch count via image_grid_thw.
    if not text_input or not text_input.strip():
        logger.warning(
            "[qwen] apply_chat_template returned empty string — "
            "slow tokenizer detected, building chat text manually"
        )
        vision_tokens = "".join(
            "<|vision_start|><|image_pad|><|vision_end|>" for _ in page_images
        )
        # System prompt is required for Qwen2-VL instruction-following mode;
        # without it the model generates narrative summaries instead of structured output.
        text_input = (
            "<|im_start|>system\n"
            "You are an expert insurance document parser. Follow the output format instructions exactly.\n"
            "<|im_end|>\n"
            f"<|im_start|>user\n{vision_tokens}{prompt}<|im_end|>\n<|im_start|>assistant\n"
        )
        logger.info("[qwen] Manual text_input length: %d chars", len(text_input))

    inputs = _qwen_processor(
        text=[text_input],
        images=page_images,
        padding=True,
        return_tensors="pt",
    ).to(_qwen_model.device)

    if inputs["input_ids"].shape[1] == 0:
        shapes = {k: tuple(v.shape) for k, v in inputs.items() if hasattr(v, "shape")}
        raise ValueError(
            f"Qwen processor returned empty input_ids — "
            f"images={len(page_images)}, text_len={len(text_input)}, "
            f"input shapes={shapes}"
        )

    with torch.inference_mode():
        generated_ids = _qwen_model.generate(**inputs, max_new_tokens=3072, do_sample=False)

    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
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

    # Detect digital vs scanned
    import fitz as _fitz
    _doc = _fitz.open(pdf_path)
    _embedded = "".join(p.get_text("text") for p in _doc).strip()
    _doc.close()
    pdf_type = "digital" if len(_embedded) > 100 else "scanned"

    # Fast path for digital PDFs: RunPod-local native extraction only.
    if pdf_type == "digital":
        fields, raw_text = _extract_digital_native(pdf_path, preextracted_text=_embedded)
        return {
            "form_type_detected": f"acord{form_type}",
            "pdf_type": "digital",
            "extracted_json": fields,
            "full_text": raw_text,
            "markdown": "",
            "source": "runpod_native",
        }

    images = _pdf_to_images(pdf_path)
    if not images:
        return {"error": "No pages found in PDF"}

    # ── Step 1: Surya + Docling in parallel (failures are non-fatal) ─────────
    surya_ocr_text: str = ""
    docling_result: Dict[str, Any] = {"markdown": "", "tables": [], "kv_pairs": {}}
    arm_warnings: List[str] = []

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_surya = pool.submit(_run_surya_ocr, images)
        future_docling = pool.submit(_run_docling, pdf_path)

        for future in as_completed([future_surya, future_docling]):
            if future is future_surya:
                try:
                    surya_ocr_text = future.result()
                except Exception as exc:
                    logger.warning("Surya OCR arm failed — Qwen2-VL will extract from images only: %s", exc)
                    arm_warnings.append(f"Surya OCR unavailable: {exc}")
            else:
                try:
                    docling_result = future.result()
                except Exception as exc:
                    logger.warning("Docling arm failed — Qwen2-VL will extract from images only: %s", exc)
                    arm_warnings.append(f"Docling unavailable: {exc}")

    # ── Step 2: Qwen2-VL always runs — uses images + whatever arms produced ──
    qwen_result = _run_qwen_extraction(images, surya_ocr_text, docling_result, form_type)

    extracted_fields = qwen_result["fields"]

    # ── Step 3: OCR fallback when Qwen produced a narrative instead of JSON ──
    # No hardcoded field names. Every label: value pair found verbatim in the
    # Surya OCR text is extracted. Values are never fabricated.
    if "_raw_qwen_output" in extracted_fields and surya_ocr_text.strip():
        logger.warning("[extraction] Qwen did not output structured fields — running OCR KV scan")

        # Primary: generic OCR extraction — reads every "LABEL: value" pair in the text
        fallback_fields: Dict[str, Any] = _extract_kv_from_ocr_text(surya_ocr_text)

        # Supplement with Docling structural KV pairs (from tables / form widgets)
        if docling_result.get("kv_pairs"):
            for k, v in docling_result["kv_pairs"].items():
                if k and v and k not in fallback_fields:
                    fallback_fields[k] = v

        logger.info("[extraction] OCR fallback extracted %d fields", len(fallback_fields))

        if fallback_fields:
            extracted_fields = fallback_fields
        else:
            logger.warning("[extraction] OCR fallback found 0 fields — keeping raw Qwen output")

    result = {
        "form_type_detected": f"acord{form_type}",
        "pdf_type": pdf_type,
        "extracted_json": extracted_fields,
        "full_text": qwen_result["qwen_raw_text"] or surya_ocr_text,
        "markdown": qwen_result["qwen_markdown"] or docling_result.get("markdown", ""),
    }
    if arm_warnings:
        result["warnings"] = arm_warnings
    return result


# ── Policy Comparison helper (used by Policy Comparison Engine pod only) ──────

def extract_policy_text(pdf_path: str) -> Dict[str, Any]:
    """
    Extract plain full-text from any insurance policy PDF.

    Used by the Policy Comparison Engine. Does not perform ACORD-specific field
    extraction. For scanned PDFs, runs Surya OCR + Docling in parallel. If both
    arms fail, falls back to Qwen2-VL to extract raw text directly from images
    so the caller always receives usable text.

    Returns:
        {
            "full_text":   str,
            "markdown":    str,
            "page_count":  int,
            "pdf_type":    "digital" | "scanned",
            "warnings":    list[str],  # present only when arms degraded/failed
        }
    """
    if not Path(pdf_path).exists():
        return {"error": f"File not found: {pdf_path}", "full_text": "", "page_count": 0, "pdf_type": "unknown"}

    import fitz as _fitz

    doc = _fitz.open(pdf_path)
    page_count = len(doc)
    embedded = "".join(p.get_text("text") for p in doc).strip()
    doc.close()

    if len(embedded) > 100:
        # Digital PDF — native text layer is reliable and fast
        return {
            "full_text": embedded,
            "markdown": "",
            "page_count": page_count,
            "pdf_type": "digital",
        }

    # Scanned PDF — Surya OCR + Docling in parallel (failures are non-fatal)
    images = _pdf_to_images(pdf_path)
    if not images:
        return {"error": "No pages found", "full_text": "", "page_count": page_count, "pdf_type": "scanned"}

    ocr_text: str = ""
    docling_result: Dict[str, Any] = {"markdown": "", "tables": [], "kv_pairs": {}}
    arm_warnings: List[str] = []

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_surya = pool.submit(_run_surya_ocr, images)
        fut_docling = pool.submit(_run_docling, pdf_path)

        for future in as_completed([fut_surya, fut_docling]):
            if future is fut_surya:
                try:
                    ocr_text = future.result()
                except Exception as exc:
                    logger.warning("Surya OCR arm failed in extract_policy_text — continuing: %s", exc)
                    arm_warnings.append(f"Surya OCR unavailable: {exc}")
            else:
                try:
                    docling_result = future.result()
                except Exception as exc:
                    logger.warning("Docling arm failed in extract_policy_text — continuing: %s", exc)
                    arm_warnings.append(f"Docling unavailable: {exc}")

    full_text = ocr_text
    markdown = docling_result.get("markdown", "")

    # Both arms produced nothing — fall back to Qwen2-VL for raw text extraction
    if not full_text.strip() and not markdown.strip():
        logger.warning("Both arms failed in extract_policy_text — falling back to Qwen2-VL")
        try:
            qwen_result = _run_qwen_extraction(
                images,
                surya_ocr_text="",
                docling_result={"markdown": "", "tables": [], "kv_pairs": {}},
                form_type="policy",
            )
            full_text = qwen_result.get("qwen_raw_text") or ""
            markdown = qwen_result.get("qwen_markdown") or ""
            arm_warnings.append("Fell back to Qwen2-VL for text extraction")
        except Exception as exc:
            logger.error("Qwen2-VL fallback also failed in extract_policy_text: %s", exc)
            arm_warnings.append(f"Qwen2-VL fallback failed: {exc}")

    result: Dict[str, Any] = {
        "full_text": full_text,
        "markdown": markdown,
        "page_count": page_count,
        "pdf_type": "scanned",
    }
    if arm_warnings:
        result["warnings"] = arm_warnings
    return result
