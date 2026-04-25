"""
PDF upload + full ACORD extraction proxy routes.

Routes:
  POST /api/v1/pdf/upload                                  — upload PDF to RunPod
  GET  /api/v1/pdf/upload/{upload_id}/status               — poll upload record
  POST /api/v1/pdf/process/{upload_id}                     — trigger Surya OCR on RunPod (legacy)
  GET  /api/v1/pdf/process/{job_id}/status                 — poll OCR job status + results (legacy)
  POST /api/v1/pdf/extract/{upload_id}                     — full ACORD extraction (Surya + Qwen VL)
  POST /api/v1/pdf/extract/{upload_id}/submit-training     — store corrected sample for fine-tuning
  GET  /api/v1/pdf/training-samples                        — list stored training samples / count
  POST /api/v1/pdf/finetune/start                          — trigger RunPod fine-tuning job
"""
from __future__ import annotations

import io
import json
import re
from typing import Any, Dict, Optional

import httpx
import structlog
from fastapi import APIRouter, Body, File, Header, HTTPException, UploadFile

from app.core.config import RUNPOD_UPLOAD_BASE_URL
from app.core.supabase import verify_user

log = structlog.get_logger("pdf_upload")
router = APIRouter()

_ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _upload_base() -> str:
    base = (RUNPOD_UPLOAD_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="RUNPOD_UPLOAD_BASE_URL is not configured")
    return base


# ── helpers ───────────────────────────────────────────────────────────────────
async def _runpod_get(path: str) -> Dict[str, Any]:
    base = _upload_base()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{base}{path}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Not found on RunPod: {path}")
            resp.raise_for_status()
            return resp.json()
    except HTTPException:
        raise
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"RunPod unreachable: {type(e).__name__}: {e}")


async def _runpod_post(path: str, timeout: Optional[float] = 120.0, **kwargs: Any) -> Dict[str, Any]:
    base = _upload_base()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base}{path}", **kwargs)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"RunPod request timed out: POST {path}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"RunPod returned {e.response.status_code}: {(e.response.text or '')[:400]}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"RunPod unreachable: {type(e).__name__}: {e}")


# ── PDF type detection (CPU-only, PyMuPDF) ───────────────────────────────────
def _detect_pdf_type(content: bytes) -> tuple[str, str]:
    """Return (pdf_type, embedded_text). Uses PyMuPDF — no GPU needed."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        embedded = "".join(page.get_text("text") for page in doc).strip()
        doc.close()
        pdf_type = "digital" if len(embedded) > 100 else "scanned"
        return pdf_type, embedded
    except Exception:
        return "scanned", ""


# ── Local multi-layer extractor for digital PDFs (no AI) ─────────────────────
#
# Layer 1 — AcroForm fields   (PyMuPDF)   : embedded widget name/value pairs
# Layer 2 — Raw text          (PyMuPDF)   : full page text for display
# Layer 3 — Tables + KV       (pdfplumber): structured rows and two-column tables
# Layer 4 — Regex patterns                : ACORD-specific field detection on raw text

# Common ACORD field patterns (form-agnostic, works across 25 / 27 / 125 / 126 etc.)
_ACORD_REGEX_PATTERNS: Dict[str, str] = {
    "policy_number":       r"(?:Policy(?:\s+No\.?|\s+Number)?)\s*[:\-]\s*([A-Z0-9\-]{4,40})",
    "effective_date":      r"(?:Effective|Eff\.?\s*Date)\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    "expiration_date":     r"(?:Expiration|Exp(?:iry)?\.?\s*Date)\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    "named_insured":       r"(?:NAMED\s+INSURED|Name\s+of\s+Insured)\s*[:\-]?\s*(.{3,80})",
    "mailing_address":     r"(?:Mailing\s+Address|Address)\s*[:\-]\s*(.{5,100})",
    "producer_name":       r"(?:PRODUCER|Producer|Agency Name)\s*[:\-]\s*(.{3,80})",
    "producer_contact":    r"(?:Contact\s+Name|Contact)\s*[:\-]\s*(.{3,60})",
    "producer_phone":      r"(?:Phone|Ph\.?)\s*[:\-]\s*([\d\s\(\)\-\+\.]{7,20})",
    "producer_fax":        r"(?:Fax)\s*[:\-]\s*([\d\s\(\)\-\+\.]{7,20})",
    "producer_email":      r"(?:E-?Mail|Email)\s*[:\-]\s*([\w\.\+\-]+@[\w\.\-]+\.\w{2,})",
    "insurer_a":           r"INSURER\s+A\s*[:\-]\s*(.{3,80})",
    "insurer_b":           r"INSURER\s+B\s*[:\-]\s*(.{3,80})",
    "insurer_c":           r"INSURER\s+C\s*[:\-]\s*(.{3,80})",
    "naic_code":           r"NAIC\s*#?\s*[:\-]?\s*(\d{5})",
    "certificate_number":  r"(?:Certificate\s+(?:No\.?|Number))\s*[:\-]\s*([A-Z0-9\-]{4,30})",
    "description_of_ops":  r"(?:DESCRIPTION\s+OF\s+OPERATIONS)[^\n]*\n(.{10,500})",
    "certificate_holder":  r"(?:CERTIFICATE\s+HOLDER)\s*[:\-]?\s*(.{5,200})",
    "gl_each_occurrence":  r"(?:Each\s+Occurrence)\s*\$?\s*([\d,]+)",
    "gl_general_aggregate":r"(?:General\s+Aggregate)\s*\$?\s*([\d,]+)",
    "auto_combined_limit": r"(?:Combined\s+Single\s+Limit)\s*\$?\s*([\d,]+)",
    "umbrella_each_occ":   r"(?:UMBRELLA|EXCESS).*?Each\s+Occurrence\s*\$?\s*([\d,]+)",
    "wc_el_each_accident": r"E\.L\.\s+Each\s+Accident\s*\$?\s*([\d,]+)",
}


def _extract_digital_pdf(
    content: bytes,
    form_type: str,
    preextracted_text: str = "",
) -> tuple[Dict[str, Any], str]:
    """
    Multi-layer local extraction. Returns (fields_dict, raw_text).
    No external API calls — CPU only.

    Pass preextracted_text from _detect_pdf_type to avoid opening the PDF twice.
    """
    import fitz  # PyMuPDF

    fields: Dict[str, Any] = {}
    raw_text = preextracted_text  # reuse text already extracted during detection

    # ── Layer 1 + (optionally) 2: PyMuPDF ────────────────────────────────────
    try:
        doc = fitz.open(stream=content, filetype="pdf")

        # Layer 1: AcroForm embedded form fields (most reliable when present)
        for page in doc:
            for widget in page.widgets() or []:
                name = (widget.field_name or "").strip()
                value = widget.field_value
                if name and value is not None:
                    val = str(value).strip()
                    if val and val not in ("Off", ""):
                        fields[name] = val

        # Layer 2: Full text — only re-extract if not already supplied
        if not raw_text:
            pages_text: list[str] = []
            for page in doc:
                text = page.get_text("text").strip()
                if text:
                    pages_text.append(text)
            raw_text = "\n\n--- Page Break ---\n\n".join(pages_text)

        doc.close()
    except Exception as e:
        log.warning("digital_extract.pymupdf_failed", error=str(e))

    # ── Layer 3: pdfplumber — tables + KV rows ────────────────────────────────
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        key = str(row[0] or "").strip().rstrip(":").strip()
                        val = str(row[1] or "").strip()
                        # Only store if key looks like a label (not a number/empty)
                        if key and val and not key.isdigit() and key not in fields:
                            fields[key] = val
    except Exception as e:
        log.warning("digital_extract.pdfplumber_failed", error=str(e))

    # ── Layer 4: Regex on raw text ────────────────────────────────────────────
    if raw_text:
        for field_key, pattern in _ACORD_REGEX_PATTERNS.items():
            if field_key in fields:
                continue  # AcroForm or pdfplumber already found this
            m = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
            if m:
                value = m.group(1).strip()
                # Trim to first line for address-like fields to avoid runaway matches
                value = value.split("\n")[0].strip()
                if value:
                    fields[field_key] = value

    return fields, raw_text


# ── POST /api/v1/pdf/smart-extract ───────────────────────────────────────────
@router.post("/api/v1/pdf/smart-extract")
async def smart_extract_pdf(
    file: UploadFile = File(...),
    form_type: str = "25",
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Unified PDF extraction entry point. No external AI APIs used.

    1. Detects whether the PDF is digital or scanned (PyMuPDF, CPU-only, instant).
    2. Digital → multi-layer local extraction:
         Layer 1: AcroForm embedded fields (PyMuPDF)
         Layer 2: Full raw text (PyMuPDF)
         Layer 3: Tables + KV rows (pdfplumber)
         Layer 4: ACORD regex patterns
       Returns fields + raw_text immediately. No RunPod involvement.
    3. Scanned → uploads PDF to RunPod, returns {pdf_type, upload_id}.
       Frontend then calls POST /api/v1/pdf/extract/{upload_id} to run
       Surya OCR + Qwen VL on the RunPod GPU.
    """
    await verify_user(authorization)

    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF or DOCX accepted (got '{ext or filename}')",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    _MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // (1024*1024)} MB). Maximum allowed is 50 MB.",
        )

    pdf_type, embedded_text = _detect_pdf_type(content)
    log.info(
        "smart_extract.detected",
        filename=filename,
        pdf_type=pdf_type,
        size_bytes=len(content),
        form_type=form_type,
    )

    if pdf_type == "digital":
        log.info("smart_extract.digital_path", filename=filename)
        # Pass embedded_text so _extract_digital_pdf skips re-opening the PDF for Layer 2
        fields, full_text = _extract_digital_pdf(content, form_type, preextracted_text=embedded_text)
        log.info("smart_extract.digital_done", filename=filename, field_count=len(fields))
        return {
            "pdf_type": "digital",
            "form_type_detected": f"acord{form_type}",
            "extracted_json": fields,
            "full_text": full_text,
            "source": "local",
        }

    # Scanned path — upload to RunPod then let frontend trigger extraction
    log.info("smart_extract.scanned_path_uploading", filename=filename)
    result = await _runpod_post(
        "/upload",
        files={"file": (filename, content, file.content_type or "application/pdf")},
        params={"form_type": form_type},
    )
    log.info("smart_extract.scanned_uploaded", upload_id=result.get("upload_id"))
    return {
        "pdf_type": "scanned",
        "upload_id": result.get("upload_id"),
        "filename": result.get("filename", filename),
        "size_bytes": result.get("size_bytes", len(content)),
        "status": result.get("status", "uploaded"),
        "form_type": form_type,
    }


# ── POST /api/v1/pdf/upload ───────────────────────────────────────────────────
@router.post("/api/v1/pdf/upload")
async def upload_pdf_to_runpod(
    file: UploadFile = File(...),
    form_type: str = "25",
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Upload a PDF from the browser to the RunPod pod storage."""
    await verify_user(authorization)

    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Only PDF or DOCX accepted (got '{ext or filename}')")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    log.info("pdf_upload.forwarding", filename=filename, size_bytes=len(content), form_type=form_type)

    result = await _runpod_post(
        "/upload",
        files={"file": (filename, content, file.content_type or "application/pdf")},
        params={"form_type": form_type},
    )

    log.info("pdf_upload.done", upload_id=result.get("upload_id"), status=result.get("status"))
    return result


# ── GET /api/v1/pdf/upload/{upload_id}/status ─────────────────────────────────
@router.get("/api/v1/pdf/upload/{upload_id}/status")
async def pdf_upload_status(
    upload_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Poll RunPod for the status of a previously uploaded PDF."""
    await verify_user(authorization)
    return await _runpod_get(f"/upload/{upload_id}/status")


# ── POST /api/v1/pdf/process/{upload_id} ─────────────────────────────────────
@router.post("/api/v1/pdf/process/{upload_id}")
async def trigger_surya_ocr(
    upload_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Trigger legacy Surya-only OCR job on RunPod. Returns job_id for polling."""
    await verify_user(authorization)
    log.info("surya_ocr.trigger", upload_id=upload_id)
    result = await _runpod_post(f"/process/{upload_id}")
    log.info("surya_ocr.queued", job_id=result.get("job_id"), upload_id=upload_id)
    return result


# ── GET /api/v1/pdf/process/{job_id}/status ──────────────────────────────────
@router.get("/api/v1/pdf/process/{job_id}/status")
async def surya_ocr_status(
    job_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Poll legacy Surya OCR job status."""
    await verify_user(authorization)
    return await _runpod_get(f"/process/{job_id}/status")


# ── POST /api/v1/pdf/extract/{upload_id} — full ACORD extraction ──────────────
@router.post("/api/v1/pdf/extract/{upload_id}")
async def extract_acord_from_upload(
    upload_id: str,
    form_type_hint: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Full ACORD extraction pipeline for a PDF already uploaded to RunPod.
    Proxies to the RunPod pod's /extract/{upload_id} endpoint which runs
    Surya OCR + Qwen2-VL directly on the pod GPU.
    Long-running (30s–5min). Returns structured ACORD fields.
    """
    await verify_user(authorization)

    # Get upload metadata to resolve form_type
    meta = await _runpod_get(f"/upload/{upload_id}/status")
    form_type = form_type_hint or str(meta.get("form_type") or "25")
    filename = meta.get("filename") or "document.pdf"

    log.info("acord_extract.start", upload_id=upload_id, filename=filename, form_type=form_type)

    # No timeout — RunPod GPU inference duration is unpredictable
    result = await _runpod_post(
        f"/extract/{upload_id}",
        timeout=None,
        params={"form_type_hint": form_type},
    )

    log.info(
        "acord_extract.done",
        upload_id=upload_id,
        form_type=result.get("form_type_detected"),
        pdf_type=result.get("pdf_type"),
    )
    return result


# ── POST /api/v1/pdf/extract/{upload_id}/submit-training ─────────────────────
@router.post("/api/v1/pdf/extract/{upload_id}/submit-training")
async def submit_for_training(
    upload_id: str,
    body: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Store a corrected ACORD extraction as a RunPod fine-tuning sample.
    Sends: original_fields, corrected_fields, raw_text, form_type + upload_id
    (the upload_id links to the PDF already stored on the RunPod pod).
    """
    await verify_user(authorization)

    meta = await _runpod_get(f"/upload/{upload_id}/status")
    form_type = body.get("form_type") or str(meta.get("form_type") or "25")

    log.info("training.submit", upload_id=upload_id, form_type=form_type)

    result = await _runpod_post(
        "/training-samples",
        json={
            "upload_id": upload_id,
            "form_type": form_type,
            "original_fields": body.get("original_fields") or {},
            "corrected_fields": body.get("corrected_fields") or {},
            "raw_text": body.get("raw_text") or "",
        },
    )

    log.info("training.stored", sample_id=result.get("sample_id"), total=result.get("total_samples"))
    return result


# ── GET /api/v1/pdf/training-samples ─────────────────────────────────────────
@router.get("/api/v1/pdf/training-samples")
async def get_training_samples(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Return all stored fine-tuning samples and their count from the RunPod pod."""
    await verify_user(authorization)
    return await _runpod_get("/training-samples")


# ── POST /api/v1/pdf/training-samples ────────────────────────────────────────
@router.post("/api/v1/pdf/training-samples")
async def add_training_sample(
    body: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Add a training sample directly to RunPod without requiring an upload_id.
    Used to sync locally-saved ACORD feedbacks to the pod when Fine-tune is clicked.
    """
    await verify_user(authorization)
    log.info("training.sync_feedback", form_type=body.get("form_type"))
    return await _runpod_post("/training-samples", json={
        "upload_id": body.get("upload_id", ""),
        "form_type": body.get("form_type", "25"),
        "original_fields": body.get("original_fields") or {},
        "corrected_fields": body.get("corrected_fields") or {},
        "raw_text": body.get("raw_text") or "",
    })


# ── GET /api/v1/pdf/finetune/jobs/{job_id} ───────────────────────────────────
@router.get("/api/v1/pdf/finetune/jobs/{job_id}")
async def get_finetune_job_status(
    job_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Poll the status of a RunPod fine-tuning job. Returns phase, eval_scores, version when done."""
    await verify_user(authorization)
    return await _runpod_get(f"/finetune/jobs/{job_id}")


# ── POST /api/v1/pdf/finetune/start ──────────────────────────────────────────
@router.post("/api/v1/pdf/finetune/start")
async def start_finetune(
    body: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Trigger fine-tuning on RunPod using all stored pending training samples.
    RunPod pod reads the JSONL file + attached PDFs and runs LoRA training.
    """
    await verify_user(authorization)
    log.info("finetune.start_requested")
    result = await _runpod_post("/finetune/start", json=body)
    log.info("finetune.queued", status=result.get("status"), samples=result.get("total_samples"))
    return result
