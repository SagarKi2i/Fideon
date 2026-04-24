"""
Fideon RunPod Server
====================
Deploy this entire runpod/ folder to /workspace/runpod/ on the pod.

Endpoints:
  GET  /health                        — liveness
  GET  /readyz                        — readiness
  POST /upload                        — receive a PDF, save to /workspace/uploads/
  GET  /upload/{upload_id}/status     — poll upload record
  GET  /upload/{upload_id}/file       — download raw PDF bytes
  GET  /uploads                       — list all uploads (admin)
  POST /process/{upload_id}           — start Surya OCR job (returns job_id immediately)
  GET  /process/{job_id}/status       — poll OCR job status + results
  GET  /jobs                          — list all OCR jobs (admin)
  POST /extract/{upload_id}           — full ACORD extraction (Surya OCR + Qwen VL)

Start via:  python server.py  (or use start.sh)
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/workspace/uploads"))
PORT = int(os.getenv("UPLOAD_SERVER_PORT", "8080"))
OCR_WORKERS = int(os.getenv("OCR_WORKERS", "1"))  # 1 GPU → 1 worker

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_uploads: Dict[str, Dict[str, Any]] = {}
_ocr_jobs: Dict[str, Dict[str, Any]] = {}

# Thread pool for background OCR (GPU work runs in a thread, not async)
_executor = ThreadPoolExecutor(max_workers=OCR_WORKERS)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Fideon RunPod Server", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "upload_dir": str(UPLOAD_DIR),
        "total_uploads": len(_uploads),
        "total_jobs": len(_ocr_jobs),
        "disk_files": len(list(UPLOAD_DIR.iterdir())) if UPLOAD_DIR.exists() else 0,
    }


@app.get("/readyz")
def readyz() -> Dict[str, str]:
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    form_type: str = "25",
) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    upload_id = str(uuid.uuid4())
    safe_name = Path(file.filename).name
    dest = UPLOAD_DIR / f"{upload_id}_{safe_name}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    dest.write_bytes(content)

    record: Dict[str, Any] = {
        "upload_id": upload_id,
        "filename": safe_name,
        "form_type": form_type,
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": len(content),
        "path": str(dest),
        "status": "uploaded",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _uploads[upload_id] = record
    return record


@app.get("/upload/{upload_id}/status")
def upload_status(upload_id: str) -> Dict[str, Any]:
    record = _uploads.get(upload_id)
    if record:
        return record

    # Recover from disk after pod restart
    matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
    if matches:
        f = matches[0]
        recovered: Dict[str, Any] = {
            "upload_id": upload_id,
            "filename": f.name.split("_", 1)[-1] if "_" in f.name else f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "status": "uploaded",
            "note": "recovered from disk after pod restart",
        }
        _uploads[upload_id] = recovered
        return recovered

    raise HTTPException(status_code=404, detail=f"Upload '{upload_id}' not found")


@app.get("/upload/{upload_id}/file")
def download_upload_file(upload_id: str) -> Response:
    """Return the raw PDF bytes for a previously uploaded file."""
    record = _uploads.get(upload_id)
    if not record:
        matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
        if matches:
            record = {"upload_id": upload_id, "path": str(matches[0]), "filename": matches[0].name.split("_", 1)[-1], "status": "uploaded"}
            _uploads[upload_id] = record
        else:
            raise HTTPException(status_code=404, detail=f"Upload '{upload_id}' not found")

    pdf_path = Path(record.get("path", ""))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF file not on disk: {pdf_path}")

    return Response(content=pdf_path.read_bytes(), media_type="application/pdf")


@app.get("/uploads")
def list_uploads() -> List[Dict[str, Any]]:
    return list(_uploads.values())


# ---------------------------------------------------------------------------
# Surya OCR — background job runner
# ---------------------------------------------------------------------------
def _run_ocr_job(job_id: str, pdf_path: str) -> None:
    """
    Runs in a thread-pool worker.
    Updates _ocr_jobs[job_id] with status transitions and final results.
    """
    job = _ocr_jobs[job_id]

    try:
        job["status"] = "loading_model"
        job["loading_model_at"] = datetime.now(timezone.utc).isoformat()

        from runpod.surya_runner import run_surya_on_pdf  # lazy: heavy import

        job["status"] = "processing"
        job["processing_at"] = datetime.now(timezone.utc).isoformat()

        result = run_surya_on_pdf(pdf_path)

        if result.get("error"):
            job["status"] = "failed"
            job["error"] = result["error"]
        else:
            job["status"] = "completed"
            job["result"] = result

        job["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["completed_at"] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# POST /process/{upload_id}  — trigger OCR
# ---------------------------------------------------------------------------
@app.post("/process/{upload_id}")
def process_upload(upload_id: str) -> Dict[str, Any]:
    """
    Start a Surya OCR job for an already-uploaded PDF.
    Returns immediately with a job_id; poll /process/{job_id}/status for progress.
    """
    # Resolve the file path
    record = _uploads.get(upload_id)
    if not record:
        matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
        if matches:
            record = {
                "upload_id": upload_id,
                "path": str(matches[0]),
                "filename": matches[0].name.split("_", 1)[-1],
                "status": "uploaded",
            }
            _uploads[upload_id] = record
        else:
            raise HTTPException(status_code=404, detail=f"Upload '{upload_id}' not found")

    pdf_path = record.get("path", "")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail=f"PDF file not found on disk: {pdf_path}")

    job_id = str(uuid.uuid4())
    job: Dict[str, Any] = {
        "job_id": job_id,
        "upload_id": upload_id,
        "filename": record.get("filename", ""),
        "form_type": record.get("form_type", "25"),
        "pdf_path": pdf_path,
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    _ocr_jobs[job_id] = job

    # Submit to background thread
    _executor.submit(_run_ocr_job, job_id, pdf_path)

    return {
        "job_id": job_id,
        "upload_id": upload_id,
        "status": "queued",
        "message": "Surya OCR job queued. Poll /process/{job_id}/status for progress.",
    }


# ---------------------------------------------------------------------------
# GET /process/{job_id}/status  — poll OCR job
# ---------------------------------------------------------------------------
@app.get("/process/{job_id}/status")
def process_status(job_id: str) -> Dict[str, Any]:
    """Return current status and (when completed) extracted OCR results."""
    job = _ocr_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"OCR job '{job_id}' not found")

    # Return full job record (includes result when status == completed)
    return job


# ---------------------------------------------------------------------------
# GET /jobs  — admin utility
# ---------------------------------------------------------------------------
@app.get("/jobs")
def list_jobs() -> List[Dict[str, Any]]:
    return [
        {k: v for k, v in job.items() if k != "result"}  # strip large payloads
        for job in _ocr_jobs.values()
    ]


# ---------------------------------------------------------------------------
# POST /extract/{upload_id}  — full ACORD extraction (Surya OCR + Qwen VL)
# ---------------------------------------------------------------------------
@app.post("/extract/{upload_id}")
async def extract_acord(
    upload_id: str,
    form_type_hint: str = "25",
) -> Dict[str, Any]:
    """
    Full ACORD extraction pipeline for an already-uploaded PDF.
    Runs Surya OCR + Qwen2-VL field extraction on the pod GPU.
    Long-running (30s–5min). Returns structured ACORD fields directly.
    """
    record = _uploads.get(upload_id)
    if not record:
        matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
        if matches:
            record = {
                "upload_id": upload_id,
                "path": str(matches[0]),
                "filename": matches[0].name.split("_", 1)[-1],
                "status": "uploaded",
            }
            _uploads[upload_id] = record
        else:
            raise HTTPException(status_code=404, detail=f"Upload '{upload_id}' not found")

    pdf_path = record.get("path", "")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail=f"PDF not on disk: {pdf_path}")

    # Normalise form_type: "acord25" → "25", "25" → "25"
    ft = form_type_hint or record.get("form_type", "25")
    if isinstance(ft, str) and ft.lower().startswith("acord"):
        ft = ft[5:]

    import asyncio
    loop = asyncio.get_event_loop()

    from runpod.extractor import run_full_extraction

    result = await loop.run_in_executor(_executor, run_full_extraction, pdf_path, ft)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
