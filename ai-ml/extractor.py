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
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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

# Mutable pointer to whichever model is active (base or latest fine-tuned).
# _load_qwen() resolves the best available path on first load; reload_qwen_model()
# hot-swaps it after each successful fine-tuning cycle.
_active_model_path: str = QWEN_MODEL_ID



def _resolve_active_model_path() -> str:
    """
    Return the best available model path at load time:
      1. Already explicitly set via reload_qwen_model() (non-default _active_model_path)
      2. Latest promoted merged model in version_registry.json (if on disk)
      3. QWEN_MODEL_ID (original base model)
    """
    global _active_model_path
    if _active_model_path != QWEN_MODEL_ID:
        # Explicit override already set — honour it.
        return _active_model_path

    registry_file = Path("/workspace/fine_tuning/registry/version_registry.json")
    if registry_file.exists():
        try:
            reg = json.loads(registry_file.read_text(encoding="utf-8"))
            current_base = reg.get("current_base")
            if current_base and Path(current_base).exists() and (Path(current_base) / "config.json").exists():
                print(f"[extractor] Fine-tuned model found in registry → {current_base}")
                _active_model_path = current_base
                return current_base
        except Exception as exc:
            print(f"[extractor] Registry read warning (using base model): {exc}")

    return QWEN_MODEL_ID


def reload_qwen_model(new_model_path: str) -> None:
    """
    Hot-swap the Qwen model to a newly-promoted fine-tuned version.
    Called by job_runner.py after each successful promote_adapter().
    Thread-safe — waits for any in-progress inference to finish before swapping.
    On H100 SXM 80 GB, training and inference run simultaneously so this is
    called only at the end of the cycle to pick up the improved weights.
    """
    global _qwen_model, _qwen_processor, _qwen_loaded, _active_model_path
    print(f"[extractor] Hot-swapping Qwen model → {new_model_path}")
    with _qwen_lock:
        _qwen_model = None
        _qwen_processor = None
        _qwen_loaded = False
        _active_model_path = new_model_path
    # Re-load outside the lock so _load_qwen() can acquire it normally.
    _load_qwen()
    print(f"[extractor] Qwen model hot-swap complete (now using fine-tuned weights)")


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
        pipeline_options.do_ocr = True
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
        from transformers import AutoConfig, AutoProcessor, Qwen2VLForConditionalGeneration

        model_path = _resolve_active_model_path()
        print(f"[extractor] Loading Qwen model from: {model_path}")

        # Patch missing fields from older checkpoints that transformers 4.57+ requires.
        config = AutoConfig.from_pretrained(model_path)
        if hasattr(config, "vision_config") and not hasattr(config.vision_config, "initializer_range"):
            config.vision_config.initializer_range = 0.02

        _qwen_processor = AutoProcessor.from_pretrained(model_path)

        # H100 SXM: BF16 is natively faster than FP16 on H100 tensor cores.
        # Flash Attention 2 accelerates long-context inference (8-page documents)
        # using H100's HBM3 bandwidth. Falls back to default attention if not installed.
        _dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        _load_kw: Dict[str, Any] = {
            "config": config,
            "torch_dtype": _dtype,
            "device_map": "auto",
        }
        try:
            _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_path, attn_implementation="flash_attention_2", **_load_kw
            )
            print("[extractor] Flash Attention 2 enabled")
        except Exception:
            _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_path, **_load_kw
            )
            print("[extractor] Flash Attention 2 unavailable — using default attention")

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
        parsed = _parse_fields_section(text)

    # RAW TEXT block ends at MARKDOWN: (if present after it)
    if ri != -1:
        raw_end = mi if (mi != -1 and mi > ri) else len(text)
        raw_text = text[ri + len(raw_marker) : raw_end].strip()
    else:
        raw_text = ""

    qwen_markdown = text[mi + len(md_marker) :].strip() if mi != -1 else ""

    return parsed, raw_text, qwen_markdown


# ── Qwen2-VL prompt (split to avoid escaping JSON braces in the output format example) ────

_PROMPT_INSTRUCTIONS = """\
You are an expert insurance document parser. You are given:
1. MULTIPLE IMAGES — one per page of an insurance document (provided in order: Page 1, Page 2, ... Page N)
2. RAW TEXT from Surya OCR — concatenated across all pages
3. RAW TEXT from Docling — structured document parser output across all pages

The document may be ANY type of insurance document, including but not limited to:
  - ACORD Forms (ACORD 25, 125, 126, 127, 130, 140, etc.)
  - Policy Declaration Pages (Auto, Home, Commercial, Life, Health, etc.)
  - Certificate of Insurance
  - Endorsements / Riders
  - Insurance Binders
  - Evidence of Property Insurance
  - Loss Runs / Claims History Reports
  - Premium Finance Agreements
  - Insurance Schedules / Summaries
  - Umbrella / Excess Liability Policies
  - Workers Compensation Policies
  - Inland Marine / Floater Schedules
  - Any other insurance-related document

STEP 1 — DOCUMENT IDENTIFICATION:
Before extracting any fields, first identify:
  - Document Type (e.g., "ACORD 25 – Certificate of Liability Insurance", "Auto Policy Declaration", "Endorsement – Additional Insured")
  - Issuing Organization (e.g., insurer name, agency, or platform)
  - Form Number and Edition Date if printed on the document
  - Total number of pages
  - Line of Business (e.g., Commercial General Liability, Personal Auto, Homeowners, Workers Comp, Life, Health)
  - Whether the document is a standalone form or part of a larger policy package

Use this identification to dynamically determine which fields and sections to extract in STEP 2.

STEP 2 — FIELD EXTRACTION:
Extract ALL fields relevant to the identified document type. Do not limit extraction to a fixed field list — adapt based on what is actually present on the document.

Common field categories across document types (extract all that apply):
  PARTIES: Named Insured / Policyholder, Additional Insureds, Insurer / Company, Agency / Broker / Producer, Mortgagee / Loss Payee, Certificate Holder
  POLICY IDENTIFIERS: Policy Number, Endorsement Number, Certificate Number, Binder Number, Claim Number
  DATES: Policy Effective Date, Policy Expiration Date, Issue Date, Endorsement Effective Date, Date of Loss
  COVERAGE DETAILS: Line of Business / Coverage Type, Coverage Parts, Limits of Liability, Deductibles, Sublimits, Exclusions, Endorsements attached
  FINANCIAL: Total Premium, Per-coverage Premium breakdown, Taxes and Fees, Finance Charge / APR, Minimum Earned Premium
  INSURED PROPERTY / RISK: Mailing Address, Risk / Property Location, Vehicle(s), Driver(s), Property Description, Occupancy Type, Schedule of Values
  CHECKBOXES & ELECTIONS: All checkbox fields with their labels and states, Election options
  REMARKS & CONDITIONS: Special Conditions, Endorsement Text, Remarks / Notes

STEP 3 — OUTPUT GENERATION:
Produce the three outputs: FIELDS:, then RAW TEXT:, then MARKDOWN:"""

_PROMPT_OUTPUT_FORMAT = """\
---
OUTPUT FORMAT (follow exactly)
---

FIELDS:
{
  "document_identification": {
    "document_type": "...",
    "form_number": "...",
    "edition_date": "...",
    "issuing_organization": "...",
    "line_of_business": "...",
    "total_pages": 1,
    "is_standalone": true,
    "part_of_policy_package": null
  },
  "extraction_meta": {
    "sources_used": ["image", "surya_ocr", "docling"],
    "conflicts_detected": [],
    "low_confidence_fields": [],
    "cross_page_fields": [],
    "blank_pages": [],
    "handwritten_fields": []
  },
  "parties": {
    "named_insured": {"value": "...", "page": 1, "confidence": "high"},
    "additional_insureds": [],
    "insurer": {"value": "...", "page": 1, "confidence": "high"},
    "agency": {"value": "...", "page": 1, "confidence": "high"},
    "broker_producer": {"value": "...", "page": 1, "confidence": "medium"},
    "mortgagee_loss_payee": {"value": "...", "page": 1, "confidence": "high"},
    "certificate_holder": {"value": "...", "page": 1, "confidence": "high"}
  },
  "policy_identifiers": {
    "policy_number": {"value": "...", "page": 1, "confidence": "high"},
    "endorsement_number": {"value": "...", "page": 1, "confidence": "high"},
    "certificate_number": {"value": "...", "page": 1, "confidence": "high"},
    "binder_number": {"value": "...", "page": 1, "confidence": "medium"}
  },
  "dates": {
    "effective_date": {"value": "...", "page": 1, "confidence": "high"},
    "expiration_date": {"value": "...", "page": 1, "confidence": "high"},
    "issue_date": {"value": "...", "page": 1, "confidence": "high"},
    "endorsement_effective_date": {"value": "...", "page": 1, "confidence": "medium"}
  },
  "insured_address": {
    "mailing_address": {"value": "...", "page": 1, "confidence": "high"},
    "city": {"value": "...", "page": 1, "confidence": "high"},
    "state": {"value": "...", "page": 1, "confidence": "high"},
    "zip_code": {"value": "...", "page": 1, "confidence": "high"},
    "risk_location": {"value": "...", "page": 1, "confidence": "medium"}
  },
  "coverages": [
    {
      "coverage_name": "...",
      "limit": "...",
      "deductible": "...",
      "premium": "...",
      "sublimit": "...",
      "page": 1,
      "confidence": "high"
    }
  ],
  "financial_summary": {
    "total_premium": {"value": "...", "page": 1, "confidence": "high"},
    "taxes_and_fees": {"value": "...", "page": 1, "confidence": "medium"},
    "minimum_earned_premium": {"value": "...", "page": 1, "confidence": "low"}
  },
  "vehicles": [],
  "drivers": [],
  "properties": [],
  "checkboxes": [
    {
      "label": "...",
      "checked": true,
      "mark_type": "tick",
      "page": 1,
      "confidence": "high"
    }
  ],
  "remarks_and_conditions": [
    {"text": "...", "page": 1, "confidence": "medium"}
  ],
  "additional_fields": {}
}

RAW TEXT:
=== PAGE 1 ===
<Fused verbatim text for page 1 from image + Surya OCR + Docling, preserving reading order.
Where sources agree, use that text. Where they disagree, use the most legible/complete version
and annotate with [reconciled] if needed.>

MARKDOWN:
# Insurance Document Summary

> Document Type: [identified document type]
> Issuing Organization: [insurer / agency name]
> Form / Policy Number: [form number and/or policy number]
> Total Pages: N
> Line of Business: [e.g., Commercial General Liability]
> Overall Confidence: High / Medium / Low

---

## General Information
| Field | Value | Page | Confidence |
|-------|-------|------|------------|
| Document Type | ... | 1 | high |
| Policy Number | ... | 1 | high |
| Effective Date | ... | 1 | high |
| Expiration Date | ... | 1 | high |

## Named Insured & Parties
| Field | Value | Page | Confidence |
|-------|-------|------|------------|
| Named Insured | ... | 1 | high |
| Insurer / Company | ... | 1 | high |
| Agency / Broker | ... | 1 | high |
| Certificate Holder | ... | 1 | high |

## Coverage Summary
| Coverage | Limit | Deductible | Premium | Page | Confidence |
|----------|-------|------------|---------|------|------------|
| ... | ... | ... | ... | 1 | high |

## Checkboxes & Elections
| Option | Status | Page |
|--------|--------|------|
| <label> | Checked (tick) | 1 |
| <label> | Unchecked | 1 |

## Remarks / Special Conditions
(Verbatim text from remarks or conditions boxes.)

## Extraction Notes
| Issue Type | Detail |
|------------|--------|
| Document Identified As | [document type and reasoning] |
| Source Conflict | <field>: Surya vs Docling disagreement — image used as tiebreaker |

---

RULES:
- ALWAYS begin with document identification before any field extraction.
- Dynamically include or exclude sections based on what is actually present. Do not render empty sections.
- Process pages sequentially; merge continuation tables across pages.
- Repeated header fields across pages: extract once, note page range if identical, flag as conflict if values differ.
- Blank/boilerplate-only pages: note in extraction_meta.blank_pages, skip detailed extraction.
- Endorsement pages: extract as a named section under "endorsements" in FIELDS.
- Checkbox CHECKED if it contains: tick (✓), X, cross (×), filled square (■), circle (●), or any handwritten mark. UNCHECKED only if completely empty. Image is primary; OCR is supporting evidence.
- Confidence: "low" = one source only, "medium" = two sources agree or partial image confirmation, "high" = all three agree or image + one OCR agree clearly.
- Output ONLY the three blocks (FIELDS, RAW TEXT, MARKDOWN) — no commentary outside them."""

_NL_SUMMARY_PROMPT = """\
You are a senior insurance document analyst. You have been given structured extraction data from an insurance document and the full raw document text. Write a comprehensive, detailed, professional natural language summary covering every piece of information present in the document.

DATA STRUCTURE GUIDE:
The extracted JSON uses a nested schema. Navigate it as follows:
- document_identification: document_type, form_number, edition_date, issuing_organization, line_of_business, total_pages
- parties: named_insured.value, insurer.value, agency.value, broker_producer.value, certificate_holder.value, additional_insureds (array), mortgagee_loss_payee.value
- policy_identifiers: policy_number.value, certificate_number.value, endorsement_number.value, binder_number.value
- dates: effective_date.value, expiration_date.value, issue_date.value, endorsement_effective_date.value
- insured_address: mailing_address.value, city.value, state.value, zip_code.value, risk_location.value
- coverages: array of objects — each has coverage_name, limit, deductible, premium, sublimit
- financial_summary: total_premium.value, taxes_and_fees.value, minimum_earned_premium.value
- vehicles: array — each has year, make, model, vin, usage
- drivers: array — each has name, dob, license_number, state
- properties: array — each has location, construction_type, occupancy, value
- checkboxes: array — each has label, checked (true/false), mark_type
- remarks_and_conditions: array of text blocks
- additional_fields: any other captured fields

PARAGRAPH-BY-PARAGRAPH WRITING PLAN (write each paragraph that has data):
Paragraph 1 — Document Overview: State the document type, form number, edition date, issuing organization, and line of business. State whether it is standalone or part of a policy package and the total number of pages.
Paragraph 2 — Parties: Name the named insured with full address (street, city, state, ZIP). Name the insurer/company. Name the producer/agency/broker with contact details if present. Name any additional insureds.
Paragraph 3 — Policy Identification & Dates: State all policy numbers, certificate numbers, endorsement numbers, and binder numbers present. State the effective and expiration dates, issue date, and any endorsement effective dates.
Paragraph 4 — General Liability Coverage: For each General Liability coverage entry found in the coverages array, state the exact coverage name, each-occurrence limit, general aggregate, products-completed operations aggregate, personal and advertising injury limit, damage-to-rented-premises limit, medical expense limit, and deductible. Note if it is occurrence-based or claims-made.
Paragraph 5 — Automobile Coverage: For each auto coverage entry, state the combined single limit or BI/PD split limits and deductibles. List every scheduled vehicle with year, make, model, VIN, and usage. Note coverage triggers (any auto, owned, hired, non-owned).
Paragraph 6 — Workers Compensation & Employers Liability: State the WC statutory limits by state, employers liability each-accident limit, disease-per-employee limit, and disease-policy limit.
Paragraph 7 — Umbrella / Excess Liability: State each occurrence and aggregate limits, the retained limit/SIR, and which underlying policies the umbrella follows.
Paragraph 8 — Other Coverages: Summarise any remaining coverage entries (inland marine, property, professional liability, cyber, crime, etc.) with their limits and deductibles.
Paragraph 9 — Drivers (if present): For each driver, state name, date of birth, license number, and issuing state.
Paragraph 10 — Properties / Locations (if present): For each property, state the address, construction type, occupancy, and insured value.
Paragraph 11 — Financial Summary: State the total premium. State per-coverage premium breakdown if available. State taxes, fees, and minimum earned premium if present.
Paragraph 12 — Checkboxes & Elections: Describe all checked options (e.g. "The form indicates this is a claims-made policy", "Waiver of subrogation applies"). Skip unchecked options unless the label adds context.
Paragraph 13 — Remarks, Special Conditions & Endorsements: Quote or closely paraphrase the full text of every remarks box, description of operations, special condition, and endorsement narrative. Do not truncate.
Paragraph 14 — Certificate Holder & Additional Insured Provisions: State the certificate holder's full name and address. State whether the certificate holder is also an additional insured. State any cancellation notice provisions (e.g. 30-day written notice). Note any waivers of subrogation.

STRICT STYLE RULES:
- Write in flowing paragraphs — no bullet points, no numbered lists, no headings, no JSON, no markdown
- Use exact dollar figures as written on the form (e.g. "$1,000,000" or "$2,000,000 aggregate")
- Omit any paragraph whose section is completely empty — do not write placeholder text
- Never write "not provided", "N/A", "none", or "not applicable"
- Do NOT copy-paste raw OCR text verbatim — synthesise into professional prose
- Tone: factual, precise, professional — suitable for a claims adjuster, underwriter, or broker
- Minimum length: 6 paragraphs for a full policy document; shorter only for single-page endorsements or binders

EXTRACTED DATA (JSON):
{fields_json}

RAW DOCUMENT TEXT (use for any detail absent from the JSON):
{raw_text}

Write the comprehensive natural language summary now:"""


def _generate_nl_summary_qwen(extracted_json: Dict[str, Any], raw_text: str) -> Optional[str]:
    """Generate NL summary using the already-loaded Qwen model (text-only inference, no images)."""
    enabled = os.getenv("ACORD_NL_SUMMARY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    try:
        _load_qwen()
        import torch
        from qwen_vl_utils import process_vision_info

        fields_json = json.dumps(extracted_json, indent=2, ensure_ascii=False)[:20000]
        raw_snippet = (raw_text or "")[:20000]
        prompt = _NL_SUMMARY_PROMPT.format(fields_json=fields_json, raw_text=raw_snippet)

        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        text_input = _qwen_processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = _qwen_processor(
            text=[text_input],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(_qwen_model.device)

        with torch.no_grad():
            generated_ids = _qwen_model.generate(**inputs, max_new_tokens=2048, temperature=0.3, do_sample=True)

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        output_text = _qwen_processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        summary = output_text.strip()
        return summary if len(summary) > 100 else None
    except Exception as exc:
        print(f"[extractor] NL summary generation failed (non-fatal): {exc}")
        return None


# ── Qwen2-VL inference ────────────────────────────────────────────────────────

def _run_qwen_extraction(
    images: List,
    surya_ocr_text: str,
    docling_result: Dict[str, Any],
    form_type: str,
) -> Dict[str, Any]:
    _load_qwen()
    import torch
    from qwen_vl_utils import process_vision_info

    # Send up to 4 pages so multi-page forms (125, 140, etc.) are fully covered
    # H100 SXM 80 GB: process up to 8 pages (vs 4 on smaller GPUs).
    # Each page ~2K vision tokens; 8 pages still fits within Qwen2-VL's 32K context
    # alongside the OCR text and instructions.
    page_images = images[:8]

    # Build INPUT CONTEXT section injected between instructions and output format.
    # Large windows: Qwen2-VL 7B has ~32K token context; images occupy ~2K tokens,
    # leaving ~30K tokens (~120K chars) for text — use as much as the document needs.
    context_parts: List[str] = [f"IMAGES: Pages 1 to {len(page_images)} (attached in order above)"]
    if surya_ocr_text.strip():
        context_parts.append(f"SURYA OCR TEXT (all pages):\n{surya_ocr_text[:20000]}")
    docling_md = docling_result.get("markdown", "").strip()
    if docling_md:
        context_parts.append(f"DOCLING TEXT (all pages):\n{docling_md[:12000]}")
    elif docling_result.get("kv_pairs"):
        kv_str = "\n".join(f"{k}: {v}" for k, v in list(docling_result["kv_pairs"].items())[:120])
        context_parts.append(f"DOCLING KV PAIRS:\n{kv_str}")
    if docling_result.get("tables"):
        tables_str = "\n\n".join(docling_result["tables"][:10])
        context_parts.append(f"DOCLING TABLES:\n{tables_str[:4000]}")

    context_section = "---\nINPUT CONTEXT\n---\n\n" + "\n\n".join(context_parts)
    prompt = _PROMPT_INSTRUCTIONS + "\n\n" + context_section + "\n\n" + _PROMPT_OUTPUT_FORMAT

    content: List[Dict[str, Any]] = [
        {"type": "image", "image": img} for img in page_images
    ]
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    text_input = _qwen_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # process_vision_info handles PIL image resizing/normalization for Qwen2-VL
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = _qwen_processor(
        text=[text_input],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(_qwen_model.device)

    # Two inference attempts — Qwen sampling is stochastic; a second draw usually
    # succeeds when the first truncates or omits the FIELDS: JSON block.
    # inputs is already on GPU so retrying costs only one extra generate() call.
    failed_previews: List[str] = []
    for attempt in range(1, 3):
        with torch.no_grad():
            generated_ids = _qwen_model.generate(**inputs, max_new_tokens=4096)

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        output_text = _qwen_processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        parsed, qwen_raw_text, qwen_markdown = _parse_qwen_output(output_text)
        if parsed is not None:
            if attempt > 1:
                print(f"[extractor] Qwen parse succeeded on attempt {attempt}.")
            return {"fields": parsed, "qwen_raw_text": qwen_raw_text, "qwen_markdown": qwen_markdown}

        preview = output_text[:500]
        failed_previews.append(f"Attempt {attempt}:\n{preview}")
        print(f"[extractor] Attempt {attempt}/2: Qwen JSON parse failed.\nPreview:\n{preview}")
        if attempt < 2:
            print("[extractor] Retrying Qwen inference with same inputs…")

    raise RuntimeError(
        "Qwen did not produce valid JSON in the FIELDS section after 2 attempts. "
        "Check model output above.\n\n" + "\n\n".join(failed_previews)
    )


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
        # Embed the complete raw text inside extracted_json so it appears in the
        # Fields/JSON/Markdown tabs and is stored in fine-tuning samples.
        fields["raw_text"] = raw_text
        nl_summary = _generate_nl_summary_qwen(fields, raw_text)
        result: Dict[str, Any] = {
            "form_type_detected": f"acord{form_type}",
            "pdf_type": "digital",
            "extracted_json": fields,
            "full_text": raw_text,
            "markdown": "",
            "source": "runpod_native",
        }
        if nl_summary:
            result["natural_language_summary"] = nl_summary
        return result

    images = _pdf_to_images(pdf_path)
    if not images:
        return {"error": "No pages found in PDF"}

    # ── Step 1: Surya + Docling in parallel ───────────────────────────────────
    surya_ocr_text: str = ""
    docling_result: Dict[str, Any] = {"markdown": "", "tables": [], "kv_pairs": {}}

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_surya = pool.submit(_run_surya_ocr, images)
        future_docling = pool.submit(_run_docling, pdf_path)

        for future in as_completed([future_surya, future_docling]):
            if future is future_surya:
                try:
                    surya_ocr_text = future.result()
                except Exception as exc:
                    print(f"[extractor] WARNING: Surya OCR failed (proceeding with empty text): {exc}")
                    surya_ocr_text = ""
            else:
                try:
                    docling_result = future.result()
                except Exception as exc:
                    print(f"[extractor] WARNING: Docling raised exception: {exc}")
                    docling_result = {"markdown": "", "tables": [], "kv_pairs": {}}
                else:
                    if docling_result.get("error"):
                        print(f"[extractor] WARNING: Docling failed: {docling_result['error']}")
                        docling_result = {"markdown": "", "tables": [], "kv_pairs": {}}

    # ── Step 2: Qwen2-VL with both arm outputs ────────────────────────────────
    qwen_result = _run_qwen_extraction(images, surya_ocr_text, docling_result, form_type)
    final_fields = qwen_result["fields"]
    # full_text: prefer Qwen's fused RAW TEXT (higher quality); fall back to complete Surya OCR
    final_raw_text = qwen_result["qwen_raw_text"] or surya_ocr_text
    # Always embed the complete Surya OCR text inside extracted_json so it appears in
    # the Fields/JSON/Markdown tabs and is stored in fine-tuning samples.
    final_fields["raw_text"] = surya_ocr_text or final_raw_text

    nl_summary = _generate_nl_summary_qwen(final_fields, final_raw_text)
    scanned_result: Dict[str, Any] = {
        "form_type_detected": f"acord{form_type}",
        "pdf_type": pdf_type,
        "extracted_json": final_fields,
        "full_text": final_raw_text,
        "markdown": qwen_result["qwen_markdown"] or docling_result.get("markdown", ""),
    }
    if nl_summary:
        scanned_result["natural_language_summary"] = nl_summary
    return scanned_result
