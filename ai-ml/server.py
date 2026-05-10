"""
Fideon RunPod Server
====================
Deploy this entire ai-ml/ folder to /workspace/ai-ml/ on the pod.

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

  Training / Fine-tuning:
  POST /training-samples              — store corrected extraction sample
  GET  /training-samples              — list stored samples + count
  POST /finetune/start                — ingest pending samples + launch run_cycle()
  GET  /finetune/jobs/{job_id}        — poll fine-tuning job status
  GET  /finetune/jobs                 — list all fine-tuning jobs
  GET  /registry/versions             — SLM version history

Start via:  python server.py  (or use start.sh)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure ai-ml/fine_tuning is resolved before any /workspace/fine_tuning that
# may exist from the backend. Insert the directory containing this file (i.e.
# /workspace/ai-ml) at the front of sys.path so `import fine_tuning` always
# picks up the correct QLoRA pipeline package.
_THIS_DIR = str(Path(__file__).parent.resolve())
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import uvicorn
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/workspace/uploads"))
TRAINING_SAMPLES_FILE = Path(os.getenv("TRAINING_SAMPLES_FILE", "/workspace/training_samples.jsonl"))
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
# Model preload at startup — eliminates 524 timeout on first real request.
# Models are loaded in a background thread so uvicorn becomes ready
# immediately (health/readyz pass) while GPU loading continues.
# ---------------------------------------------------------------------------
def _preload_models() -> None:
    try:
        from extractor import _load_surya, _load_docling, _load_qwen
        print("[preload] Loading Surya OCR...", flush=True)
        _load_surya()
        print("[preload] Loading Docling...", flush=True)
        _load_docling()
        print("[preload] Loading Qwen2-VL...", flush=True)
        _load_qwen()
        print("[preload] All models loaded — pod is fully warm.", flush=True)
    except Exception as exc:
        print(f"[preload] Model preload failed (non-fatal): {exc}", flush=True)


_executor.submit(_preload_models)


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

        from surya_runner import run_surya_on_pdf  # lazy: heavy import

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
# Extraction job store (mirrors _ocr_jobs pattern)
# ---------------------------------------------------------------------------
_extract_jobs: Dict[str, Dict[str, Any]] = {}
_extract_jobs_lock = threading.Lock()
_gpu_semaphore = threading.Semaphore(1)  # serialize GPU extraction — prevents VRAM contention

# ---------------------------------------------------------------------------
# Share-gradients job store + pending-share directory
# ---------------------------------------------------------------------------
_share_jobs: Dict[str, Dict[str, Any]] = {}
_share_jobs_lock = threading.Lock()
PENDING_SHARE_DIR = Path(os.getenv("PENDING_SHARE_DIR", "/workspace/fine_tuning/pending_shares"))


class _PeriodicLogger:
    """Prints a status line every `interval` seconds in a daemon thread.

    Use as a context manager around any blocking call to get live terminal updates:
        with _PeriodicLogger(10, lambda: f"Uploading... {elapsed}s elapsed"):
            blocking_upload()
    """
    def __init__(self, interval: float, fn):
        self._interval = interval
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=self._interval + 1)

    def _run(self):
        while not self._stop.wait(self._interval):
            try:
                print(self._fn(), flush=True)
            except Exception:
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


def _run_extract_job(job_id: str, pdf_path: str, form_type: str) -> None:
    """Background thread: full Surya + Docling + Qwen2-VL extraction."""
    import time as _time
    import traceback as _tb

    def _set(phase: str, **kwargs: Any) -> None:
        with _extract_jobs_lock:
            _extract_jobs[job_id].update({"phase": phase, **kwargs})
        print(f"[extract:{job_id[:8]}] phase={phase} {kwargs}", flush=True)

    _set("running", started_at=datetime.now(timezone.utc).isoformat())
    print(f"[extract:{job_id[:8]}] Starting extraction: pdf={pdf_path} form_type={form_type}", flush=True)
    t0 = _time.time()
    try:
        from extractor import run_full_extraction
        _set("running", step="waiting_for_gpu")
        print(f"[extract:{job_id[:8]}] Waiting for GPU semaphore...", flush=True)
        with _gpu_semaphore:
            _set("running", step="surya+docling+qwen")
            print(f"[extract:{job_id[:8]}] GPU acquired — running extraction", flush=True)
            result = run_full_extraction(pdf_path, form_type)
        elapsed = round(_time.time() - t0, 1)

        if "error" in result:
            err = result["error"]
            print(f"[extract:{job_id[:8]}] FAILED after {elapsed}s: {err}", flush=True)
            _set("failed", error=err, elapsed_s=elapsed,
                 completed_at=datetime.now(timezone.utc).isoformat())
        else:
            warnings = result.get("warnings", [])
            print(f"[extract:{job_id[:8]}] ✓ Completed in {elapsed}s"
                  f" pdf_type={result.get('pdf_type')}"
                  f" fields={len(result.get('extracted_json') or {})}"
                  f"{' warnings=' + str(warnings) if warnings else ''}", flush=True)
            _set("completed", result=result, elapsed_s=elapsed,
                 completed_at=datetime.now(timezone.utc).isoformat())

    except Exception as exc:
        elapsed = round(_time.time() - t0, 1)
        tb = _tb.format_exc()
        print(f"[extract:{job_id[:8]}] EXCEPTION after {elapsed}s: {exc}\n{tb}", flush=True)
        _set("failed",
             error=str(exc),
             traceback=tb,
             elapsed_s=elapsed,
             completed_at=datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# POST /extract/{upload_id}  — submit async ACORD extraction job
# ---------------------------------------------------------------------------
@app.post("/extract/{upload_id}")
def extract_acord(
    upload_id: str,
    form_type_hint: str = "25",
) -> Dict[str, Any]:
    """
    Submit a full ACORD extraction job (Surya OCR + Docling + Qwen2-VL).
    Returns immediately with a job_id — poll GET /extract/{job_id}/status.
    Async because Qwen2-VL inference can take 3-10 min; RunPod proxy
    has a hard ~100s HTTP timeout so synchronous extraction always 524s.
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

    # Normalise form_type: "ACORD_25" → "25", "acord25" → "25", "25" → "25"
    ft = form_type_hint or record.get("form_type", "25")
    if isinstance(ft, str):
        ftl = ft.lower()
        if ftl.startswith("acord_"):
            ft = ft[6:]
        elif ftl.startswith("acord"):
            ft = ft[5:]

    job_id = str(uuid.uuid4())
    job: Dict[str, Any] = {
        "job_id":    job_id,
        "upload_id": upload_id,
        "filename":  record.get("filename", ""),
        "form_type": ft,
        "pdf_path":  pdf_path,
        "phase":     "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    with _extract_jobs_lock:
        _extract_jobs[job_id] = job

    _executor.submit(_run_extract_job, job_id, pdf_path, ft)

    return {
        "job_id":    job_id,
        "upload_id": upload_id,
        "phase":     "queued",
        "message":   f"Extraction queued. Poll GET /extract/{job_id}/status for progress.",
    }


# ---------------------------------------------------------------------------
# GET /extract/{job_id}/status  — poll extraction job
# ---------------------------------------------------------------------------
@app.get("/extract/{job_id}/status")
def extract_status(job_id: str) -> Dict[str, Any]:
    """
    Poll an async extraction job.
    phase: queued → running → completed | failed
    When completed, 'result' contains the full extraction output.
    """
    with _extract_jobs_lock:
        job = _extract_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Extraction job '{job_id}' not found")
    return job


# ---------------------------------------------------------------------------
# POST /generate  — text generation using the loaded Qwen2-VL model
# Used by the backend's NL summary service (RUNPOD_GENERATE_URL).
# ---------------------------------------------------------------------------
@app.post("/generate")
async def generate_text(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Lightweight text generation endpoint backed by the already-loaded Qwen2-VL model.
    Accepts: { prompt, max_new_tokens, temperature, raw }
    Returns: { text }
    """
    import asyncio

    prompt: str = body.get("prompt", "")
    max_new_tokens: int = int(body.get("max_new_tokens", 2048))
    temperature: float = float(body.get("temperature", 0.3))

    if not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    def _infer() -> str:
        import extractor as _ext
        import torch

        # _load_qwen() sets extractor._qwen_model / _qwen_processor as module globals.
        # Access them through the module after loading so we always get the live reference,
        # not a None snapshot captured before the model was loaded.
        _ext._load_qwen()
        model     = _ext._qwen_model
        processor = _ext._qwen_processor

        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        text_input = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        # Slow tokenizer (no tokenizer.json in checkpoint) returns "" even for
        # text-only messages when chat_template is missing from tokenizer_config.json.
        if not text_input or not text_input.strip():
            text_input = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

        inputs = processor(
            text=[text_input],
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        if inputs["input_ids"].shape[1] == 0:
            raise ValueError("Processor returned empty input_ids for /generate request")

        use_sampling = temperature > 0
        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=use_sampling,
                temperature=temperature if use_sampling else None,
            )

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        return processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(_executor, _infer)
    return {"text": text}


# ---------------------------------------------------------------------------
# Training samples — persist across pod restarts via JSONL on disk
# ---------------------------------------------------------------------------

def _pdf_path_for_upload(upload_id: str) -> Optional[str]:
    record = _uploads.get(upload_id)
    if record:
        return record.get("path")
    matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
    return str(matches[0]) if matches else None


def _load_training_samples() -> List[Dict[str, Any]]:
    if not TRAINING_SAMPLES_FILE.exists():
        return []
    samples = []
    for line in TRAINING_SAMPLES_FILE.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return samples


# ── Supabase training_feedback helpers ────────────────────────────────────────

def _fetch_unused_training_feedback() -> List[Dict[str, Any]]:
    """Fetch rows from Supabase training_feedback where is_used_for_training=false."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        return []
    try:
        import httpx
        resp = httpx.get(
            f"{supabase_url}/rest/v1/training_feedback",
            params={"is_used_for_training": "eq.false", "select": "*"},
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        print(f"[finetune] Could not fetch training_feedback from Supabase: {exc}")
        return []


def _mark_acord_runs_approved(run_ids: List[str]) -> None:
    """Set status='approved' on acord_extraction_runs rows so they leave the training queue.
    Uses the mark_acord_runs_approved RPC (SECURITY DEFINER) to bypass RLS."""
    if not run_ids:
        return
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        print("[finetune/start] Supabase not configured — skipping acord_runs approval")
        return
    try:
        import httpx
        # Call SECURITY DEFINER RPC — bypasses RLS, works for any user's runs
        resp = httpx.post(
            f"{supabase_url}/rest/v1/rpc/mark_acord_runs_approved",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            json={"run_ids": run_ids},
            timeout=15,
        )
        resp.raise_for_status()
        updated = resp.json() if resp.text.strip() else 0
        print(f"[finetune/start] Marked {updated} acord_extraction_run(s) as approved in Supabase")
    except Exception as exc:
        print(f"[finetune/start] Could not mark acord_extraction_runs as approved: {exc}")


def _mark_training_feedback_used(ids: List[str]) -> None:
    """Mark a list of training_feedback rows as used in Supabase."""
    if not ids:
        return
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        return
    try:
        import httpx
        id_list = ",".join(str(i) for i in ids)
        httpx.patch(
            f"{supabase_url}/rest/v1/training_feedback",
            params={"id": f"in.({id_list})"},
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            json={"is_used_for_training": True},
            timeout=10,
        )
    except Exception as exc:
        print(f"[finetune] Could not mark training_feedback as used: {exc}")


@app.post("/training-samples")
async def store_training_sample(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Store one corrected extraction as a fine-tuning sample.
    Called after the user edits and approves the extracted fields.
    Each sample written as a JSONL line so it survives pod restarts.
    """
    upload_id = body.get("upload_id", "")
    pdf_path = _pdf_path_for_upload(upload_id) or ""

    # Normalise form_type so ingest.py never sees "ACORD_25" / "acord25" variants
    raw_ft = str(body.get("form_type") or "25")
    ftl = raw_ft.lower()
    if ftl.startswith("acord_"):
        raw_ft = raw_ft[6:]
    elif ftl.startswith("acord"):
        raw_ft = raw_ft[5:]

    sample: Dict[str, Any] = {
        "sample_id": str(uuid.uuid4()),
        "upload_id": upload_id,
        "pdf_path": pdf_path,
        "form_type": raw_ft,
        "original_fields": body.get("original_fields") or {},
        "corrected_fields": body.get("corrected_fields") or {},
        "raw_text": body.get("raw_text", ""),
        "run_id": body.get("run_id") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    with open(TRAINING_SAMPLES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(sample) + "\n")

    total = len(_load_training_samples())
    return {
        "status": "stored",
        "sample_id": sample["sample_id"],
        "total_samples": total,
    }


@app.get("/training-samples")
def list_training_samples() -> Dict[str, Any]:
    """List all stored training samples (summary for status/count display)."""
    samples = _load_training_samples()
    return {
        "total_samples": len(samples),
        "pending": sum(1 for s in samples if s.get("status") == "pending"),
        "samples": [
            {
                "sample_id": s.get("sample_id"),
                "upload_id": s.get("upload_id"),
                "form_type": s.get("form_type"),
                "created_at": s.get("created_at"),
                "status": s.get("status"),
            }
            for s in samples
        ],
    }


@app.post("/finetune/start")
async def start_finetune(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """
    Convert all pending training samples to chat-format, snapshot them to
    a versioned JSONL, then launch run_cycle() in a background thread.

    Returns immediately with job_id for polling via GET /finetune/jobs/{job_id}.
    """
    import asyncio
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.continuous_learning.version_store import append_training_sample
    from fine_tuning.job_runner import launch_cycle_background

    # acord_run_ids are passed by the frontend for reference only.
    # Runs are marked approved AFTER training completes (not here) so that
    # samples remain visible in Training Samples if the job fails.
    explicit_run_ids: List[str] = [
        str(rid) for rid in (body.get("acord_run_ids") or []) if rid
    ]

    samples = [s for s in _load_training_samples() if s.get("status") == "pending"]
    if not samples:
        return {
            "status": "no_samples",
            "message": "No pending training samples found.",
            "total_samples": 0,
        }

    ft_config_path = os.getenv(
        "FINE_TUNING_CONFIG_PATH",
        str(Path(__file__).parent / "fine_tuning" / "config.yaml"),
    )

    # ── Load continuous-learning config ───────────────────────────────────────
    try:
        from fine_tuning.config_schema import load_and_validate_config
        ft_cfg = load_and_validate_config(ft_config_path)
    except Exception as e:
        return {"status": "error", "message": f"Could not load fine-tuning config: {e}"}

    cl_cfg       = ft_cfg.get("continuous_learning", {})
    feedback_dir = Path(cl_cfg.get("feedback_datasets_dir",
                                   "/workspace/fine_tuning/datasets/feedback_learning"))
    threshold    = int(cl_cfg.get("retrain_threshold", 25))

    # ── Build chat-format samples and append to version store ─────────────────
    snapshot_path: Optional[str] = None
    ingested = 0
    ingested_ids: set = set()   # only successfully processed samples get marked "used"
    for sample in samples:
        try:
            chat_row = build_training_sample_from_correction(
                run_row=sample,
                corrected_json=sample.get("corrected_fields") or {},
            )
            outcome = append_training_sample(
                root=feedback_dir,
                row=chat_row,
                retrain_threshold=threshold,
            )
            ingested += 1
            ingested_ids.add(sample.get("sample_id"))
            if outcome.version_snapshot_path:
                snapshot_path = outcome.version_snapshot_path
        except Exception as exc:
            print(f"[finetune/start] skipping sample {sample.get('sample_id')} (stays pending for retry): {exc}")

    if not snapshot_path:
        # Force a snapshot from whatever is pending now (manual trigger bypasses threshold)
        import json as _json
        pending_file = feedback_dir / "pending.jsonl"
        if pending_file.exists() and pending_file.stat().st_size > 0:
            from fine_tuning.continuous_learning.version_store import (
                _load_manifest, _save_manifest, _version_path, _pending_path,
            )
            manifest = _load_manifest(feedback_dir)
            version  = int(manifest.get("next_version", 1))
            vp = _version_path(feedback_dir, version)
            vp.parent.mkdir(parents=True, exist_ok=True)
            vp.write_bytes(pending_file.read_bytes())
            pending_file.write_text("", encoding="utf-8")
            manifest["pending_count"]  = 0
            manifest["next_version"]   = version + 1
            manifest.setdefault("snapshots", []).append({
                "version":    version,
                "path":       str(vp),
                "rows":       ingested,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            _save_manifest(feedback_dir, manifest)
            snapshot_path = str(vp)
        else:
            return {
                "status": "no_data",
                "message": "Samples ingested but no training data in pending store.",
                "ingested": ingested,
            }

    # ── Mark successfully ingested samples as "used" — skipped ones stay pending ──
    used_ids = ingested_ids
    all_samples = _load_training_samples()
    used_at = datetime.now(timezone.utc).isoformat()
    updated_samples = []
    for s in all_samples:
        if s.get("sample_id") in used_ids:
            s["status"] = "used"
            s["used_at"] = used_at
        updated_samples.append(s)
    TRAINING_SAMPLES_FILE.write_text(
        "\n".join(json.dumps(s) for s in updated_samples) + "\n",
        encoding="utf-8",
    )

    # ── Launch cycle in background thread ─────────────────────────────────────
    job_id = str(uuid.uuid4())
    launch_cycle_background(
        config_path=ft_config_path,
        new_data_path=snapshot_path,
        job_id=job_id,
    )

    return {
        "status": "queued",
        "job_id": job_id,
        "message": (
            f"Fine-tuning started with {ingested} sample(s). "
            f"Poll GET /finetune/jobs/{job_id} for progress."
        ),
        "total_samples": ingested,
        "snapshot_path": snapshot_path,
    }


@app.get("/finetune/jobs/{job_id}")
def finetune_job_status(job_id: str) -> Dict[str, Any]:
    """
    Poll the status of a fine-tuning job launched via POST /finetune/start.

    Phases: starting → loading_config → building_dataset → resolving_base_model
            → training → evaluating → gate_checked → merging → promoting → done

    Status values: running | completed | gate_failed | failed
    """
    from fine_tuning.job_runner import get_job_status
    job = get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Fine-tuning job '{job_id}' not found")
    return job


@app.get("/finetune/jobs")
def list_finetune_jobs() -> Dict[str, Any]:
    """List all fine-tuning jobs tracked in this server session."""
    from fine_tuning.job_runner import _jobs
    return {
        "total": len(_jobs),
        "jobs": [
            {
                "job_id":      jid,
                "status":      j.get("status"),
                "phase":       j.get("phase"),
                "version":     j.get("version"),
                "started_at":  j.get("started_at"),
                "finished_at": j.get("finished_at"),
            }
            for jid, j in _jobs.items()
        ],
    }


@app.get("/registry/versions")
def list_registry_versions() -> Dict[str, Any]:
    """Return the full version registry (SLM version history)."""
    registry_path = os.getenv(
        "VERSION_REGISTRY_PATH",
        "/workspace/fine_tuning/registry/version_registry.json",
    )
    try:
        from fine_tuning.registry.version_registry import VersionRegistry
        reg = VersionRegistry(registry_path)
        return {
            "current_version": reg.get_current_version(),
            "current_base":    reg.get_current_base(),
            "versions":        reg.list_versions(),
        }
    except Exception as exc:
        return {"error": str(exc), "versions": []}


@app.get("/federated/registered-versions")
def get_registered_adapter_versions() -> Dict[str, Any]:
    """
    Query Supabase adapter_registry and return all registered GGUF versions,
    grouped by adapter_version descending. Used by the frontend to display
    a persistent list of globally aggregated model versions.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        return {"versions": [], "message": "Supabase not configured on pod"}
    try:
        import httpx
        from collections import defaultdict
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        q = (
            "select=adapter_version,quant_level,size_bytes,domain,created_at"
            "&is_available=eq.true&blocked=eq.false"
            "&order=adapter_version.desc"
        )
        resp = httpx.get(
            f"{supabase_url}/rest/v1/adapter_registry?{q}",
            headers=headers, timeout=10
        )
        if not resp.is_success:
            return {"versions": [], "error": f"Supabase error: {resp.status_code}"}
        rows = resp.json()
        grouped: Dict[str, list] = defaultdict(list)
        for r in rows:
            grouped[r["adapter_version"]].append(r)
        versions = [
            {
                "adapter_version": ver,
                "domain":          artifacts[0].get("domain", "acord"),
                "quant_levels":    [a["quant_level"] for a in artifacts if a["quant_level"] != "unknown"],
                "total_size_bytes": sum(a["size_bytes"] for a in artifacts),
                "registered_at":   artifacts[0].get("created_at"),
            }
            for ver, artifacts in sorted(grouped.items(), reverse=True)
        ]
        return {"versions": versions}
    except Exception as exc:
        return {"versions": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Federated Learning — FedAvg aggregation across all stored weight versions
# ---------------------------------------------------------------------------

_fed_jobs: Dict[str, Dict[str, Any]] = {}
_fed_jobs_lock = threading.Lock()


def _set_fed_job(job_id: str, data: Dict[str, Any]) -> None:
    with _fed_jobs_lock:
        _fed_jobs[job_id] = data


def _update_fed_job(job_id: str, phase: str, **kwargs: Any) -> None:
    with _fed_jobs_lock:
        if job_id in _fed_jobs:
            _fed_jobs[job_id]["phase"] = phase
            _fed_jobs[job_id].update(kwargs)


def _fedavg_safetensors(
    model_dirs: List[str], 
    output_dir: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> None:
    """
    Average safetensors weights across model_dirs → output_dir (FedAvg with equal weights).
    Falls back to copying the latest model if safetensors/torch are unavailable.
    """
    import shutil as _shutil
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    if len(model_dirs) == 1:
        _shutil.copytree(model_dirs[0], output_dir, dirs_exist_ok=True)
        print("[fedavg] Single model — copied without averaging.")
        return

    try:
        from safetensors import safe_open
        from safetensors.torch import save_file
        import torch
    except ImportError as _ie:
        raise ImportError(
            "safetensors and torch are required for FedAvg aggregation. "
            f"Install them with: pip install safetensors torch\nOriginal error: {_ie}"
        ) from _ie

    last_dir = Path(model_dirs[-1])
    # Copy all non-weight files (config.json, tokenizer, etc.) from the latest model
    for f in last_dir.iterdir():
        if f.suffix == ".safetensors":
            continue
        dest = output / f.name
        if f.is_dir():
            _shutil.copytree(str(f), str(dest), dirs_exist_ok=True)
        else:
            _shutil.copy2(str(f), str(dest))

    shards = sorted(last_dir.glob("*.safetensors"))
    if not shards:
        _shutil.copytree(model_dirs[-1], output_dir, dirs_exist_ok=True)
        return

    print(f"[fedavg] Averaging {len(model_dirs)} models across {len(shards)} shard(s)…")
    for i, shard in enumerate(shards):
        if progress_callback:
            progress_callback(shard.name, i, len(shards))
        all_tensors: Dict[str, list] = {}
        for mdir in model_dirs:
            shard_path = Path(mdir) / shard.name
            if not shard_path.exists():
                continue
            with safe_open(str(shard_path), framework="pt") as f:
                for key in f.keys():
                    all_tensors.setdefault(key, []).append(f.get_tensor(key))
        averaged = {k: torch.stack(vs).mean(dim=0) for k, vs in all_tensors.items() if vs}
        save_file(averaged, str(output / shard.name))
        print(f"[fedavg]   Averaged shard: {shard.name}")
        if progress_callback:
            progress_callback(shard.name, i + 1, len(shards))

    print(f"[fedavg] Done — aggregated model written to {output_dir}")


def _run_federated_job(job_id: str) -> None:
    """Background thread: download all stored weight versions, FedAvg, upload result."""
    import shutil as _shutil
    import tempfile

    # Shared state read by heartbeat threads across all phases
    _fed_state: Dict[str, Any] = {"filename": "", "bytes": 0, "total_bytes": 0, "shard": 0, "total_shards": 0}

    def _progress_cb(filename: str, current: int, total: Optional[int]) -> None:
        pct = (current / total * 100) if total else 0
        _fed_state["filename"] = filename
        _fed_state["bytes"] = current
        _fed_state["total_bytes"] = total or 0
        _update_fed_job(job_id, "downloading_weights", progress={
            "current_file": filename,
            "percentage": round(pct, 1),
            "transferred_bytes": current,
            "total_bytes": total
        })

    try:
        from fine_tuning.storage_client import get_storage_client
        seaweed = get_storage_client()

        # ── 1. Discover all available fine-tuned versions ────────────────────
        _update_fed_job(job_id, "discovering_versions")
        print("[global-update] ══ Step 1/5 ══ Discovering available model versions in Azure Blob …", flush=True)
        latest = seaweed.get_latest_finetuned_version()
        if latest is None:
            raise RuntimeError("No fine-tuned weights found in storage. Run Local Training first.")

        versions_available: List[int] = []
        try:
            versions_available = seaweed.list_finetuned_versions(latest)
        except Exception as exc:
            print(f"[federated] Version discovery error (using latest only): {exc}")
            versions_available = [latest]

        if not versions_available:
            versions_available = [latest]

        # ── Filter: skip versions already successfully quantized ─────────────────
        # A version with quantized/v{N}/*.gguf was processed by a prior Global Update.
        # A version without .gguf files (or no quantized/ prefix) is fresh → include.
        # If quantization previously FAILED (prefix exists but no .gguf), also include.
        print("[global-update]   Checking which versions have already been quantized …", flush=True)
        fresh_versions: List[int] = []
        already_quantized: List[int] = []
        for v in versions_available:
            if seaweed.has_successful_quantization(v):
                already_quantized.append(v)
                print(f"[global-update]   Skipping v{v} — already quantized successfully", flush=True)
            else:
                fresh_versions.append(v)
                print(f"[global-update]   Including v{v} — fresh / quantization not yet done", flush=True)

        if not fresh_versions:
            msg = (
                f"No new weights to aggregate — all {len(already_quantized)} version(s) "
                f"already quantized: {already_quantized}. "
                "Run Local Training + Share Gradients first."
            )
            print(f"[global-update] {msg}", flush=True)
            _set_fed_job(job_id, {
                **_fed_jobs.get(job_id, {}),
                "status": "completed",
                "phase": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "version": latest,
                "message": msg,
                "versions_skipped_quantized": already_quantized,
            })
            return

        print(
            f"[global-update]   Fresh versions to aggregate: {fresh_versions} | "
            f"Already quantized (skipped): {already_quantized}",
            flush=True,
        )
        versions_available = fresh_versions

        _update_fed_job(job_id, "downloading_weights", versions_aggregated=versions_available)
        print(
            f"[global-update] ══ Step 2/5 ══ Collecting weights — "
            f"versions to aggregate: {versions_available}",
            flush=True,
        )

        # ── 2. Pre-flight: ensure enough disk space on /workspace ────────────────
        import shutil as _shutil_check
        _ws_free_gb = _shutil_check.disk_usage("/workspace").free / (1024 ** 3)
        _needed_gb  = 40  # download + FedAvg copy + upload buffer (~2× model size)
        if _ws_free_gb < _needed_gb:
            raise RuntimeError(
                f"Not enough disk space on /workspace for Global Update: "
                f"{_ws_free_gb:.1f} GB free, need ≥{_needed_gb} GB. "
                "Free space by deleting old merged model directories under /workspace/fine_tuning/runs/."
            )
        print(f"[federated] Disk pre-check OK: {_ws_free_gb:.1f} GB free on /workspace")

        # ── 3. Download all versions (skip any that fail — partial FedAvg is better than none) ──
        # Use /workspace for temp dir — /tmp is a small tmpfs on RunPod and
        # the model shards are ~20 GB, which exceeds typical /tmp capacity.
        _ws_tmp = Path("/workspace/.fedavg_tmp")
        _ws_tmp.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="fedavg_", dir=str(_ws_tmp)))
        try:
            model_dirs: List[str] = []
            downloaded_versions: List[int] = []
            skipped_versions: List[int] = []
            for v in versions_available:
                local_dir = str(tmp_dir / f"v{v}")
                _fed_state["filename"] = ""
                _fed_state["bytes"] = 0
                _fed_state["total_bytes"] = 0
                _t0_dl = time.time()
                vidx = versions_available.index(v) + 1
                print(
                    f"[global-update]   Downloading v{v} from Azure Blob "
                    f"({vidx}/{len(versions_available)}) …",
                    flush=True,
                )

                def _dl_hb(ver=v, t0=_t0_dl):
                    elapsed = int(time.time() - t0)
                    fname = _fed_state["filename"]
                    cur   = _fed_state["bytes"]
                    tot   = _fed_state["total_bytes"]
                    if tot and cur:
                        return (
                            f"[global-update]   Collecting weights v{ver} → {fname} | "
                            f"{cur/1e9:.2f}/{tot/1e9:.2f} GB ({cur/tot*100:.0f}%) | {elapsed}s elapsed"
                        )
                    if fname:
                        return f"[global-update]   Collecting weights v{ver} → {fname} | {elapsed}s elapsed"
                    return f"[global-update]   Collecting weights v{ver} from Azure Blob | {elapsed}s elapsed"

                try:
                    with _PeriodicLogger(10, _dl_hb):
                        seaweed.download_finetuned_model(v, local_dir, progress_callback=_progress_cb)
                    model_dirs.append(local_dir)
                    downloaded_versions.append(v)
                    print(f"[global-update]   v{v} downloaded ✓ ({int(time.time()-_t0_dl)}s)", flush=True)
                except Exception as dl_exc:
                    print(f"[global-update]   WARNING: Skipping v{v} — download failed: {dl_exc}", flush=True)
                    skipped_versions.append(v)

            if not model_dirs:
                raise RuntimeError(
                    f"All {len(versions_available)} version(s) failed to download from storage. "
                    f"Check that {seaweed._endpoint} is reachable from the pod. "
                    f"Versions attempted: {versions_available}"
                )

            if skipped_versions:
                print(
                    f"[federated] Proceeding with {len(model_dirs)} version(s) "
                    f"(skipped {skipped_versions} due to download errors)"
                )

            # ── 4. FedAvg aggregation ─────────────────────────────────────────
            def _avg_progress(shard_name: str, current: int, total: int) -> None:
                _fed_state["filename"] = shard_name
                _fed_state["shard"] = current
                _fed_state["total_shards"] = total
                _update_fed_job(job_id, "aggregating", progress={
                    "current_file": f"Averaging: {shard_name}",
                    "percentage": round(current / total * 100, 1) if total else 100,
                    "transferred_bytes": current,
                    "total_bytes": total,
                    "unit": "shards"
                })

            _update_fed_job(job_id, "aggregating")
            agg_dir = str(tmp_dir / "aggregated")
            _fed_state["shard"] = 0
            _fed_state["total_shards"] = 0
            _t0_agg = time.time()
            print(
                f"[global-update] ══ Step 3/5 ══ Aggregating weights — "
                f"FedAvg across {len(model_dirs)} model(s) …",
                flush=True,
            )

            def _agg_hb(t0=_t0_agg):
                elapsed = int(time.time() - t0)
                shard = _fed_state["shard"]
                total_shards = _fed_state["total_shards"]
                fname = _fed_state["filename"]
                if total_shards:
                    pct = shard / total_shards * 100
                    return (
                        f"[global-update]   Aggregating weights — shard {shard}/{total_shards} "
                        f"({pct:.0f}%) | {fname} | {elapsed}s elapsed"
                    )
                return f"[global-update]   Aggregating weights (FedAvg) | {elapsed}s elapsed"

            with _PeriodicLogger(10, _agg_hb):
                _fedavg_safetensors(model_dirs, agg_dir, progress_callback=_avg_progress)
            print(f"[global-update]   FedAvg complete. ({int(time.time()-_t0_agg)}s)", flush=True)

            # B7: verify aggregated model is valid before uploading
            _agg_path = Path(agg_dir)
            if not (_agg_path / "config.json").exists():
                raise RuntimeError(
                    f"FedAvg output at {agg_dir} is missing config.json — "
                    "aggregation may have failed silently. Aborting upload."
                )

            # ── 5. Quantize aggregated model → GGUF ──────────────────────────
            _update_fed_job(job_id, "quantizing", progress={
                "current_file": "Converting to GGUF...",
                "percentage": 0,
                "transferred_bytes": 0,
                "total_bytes": 100
            })
            gguf_dir = str(tmp_dir / "gguf")
            _t0_quant = time.time()
            print(
                "[global-update] ══ Step 4/5 ══ Quantizing aggregated model → GGUF (Q5_K_M + Q4_K_M) …",
                flush=True,
            )
            try:
                from fine_tuning.quantization.quantizer import run_quantization
                with _PeriodicLogger(
                    10,
                    lambda t0=_t0_quant: (
                        f"[global-update]   Quantizing to GGUF | {int(time.time()-t0)}s elapsed"
                    ),
                ):
                    quant_results = run_quantization(agg_dir, gguf_dir, latest + 1)
                print(
                    f"[global-update]   Quantization complete — "
                    f"{len(quant_results)} GGUF(s) produced. ({int(time.time()-_t0_quant)}s)",
                    flush=True,
                )
            except Exception as exc:
                print(f"[global-update]   Quantization failed (non-fatal): {exc}", flush=True)
                quant_results = {}

            _update_fed_job(job_id, "quantizing", progress={
                "current_file": "GGUF Conversion Complete",
                "percentage": 100,
                "transferred_bytes": 100,
                "total_bytes": 100
            })

            # ── 6. Upload aggregated model + GGUFs as new version ─────────────
            def _up_progress(fname: str, cur: int, tot: Optional[int]) -> None:
                pct = (cur / tot * 100) if tot else 0
                _fed_state["filename"] = fname
                _fed_state["bytes"] = cur
                _fed_state["total_bytes"] = tot or 0
                _update_fed_job(job_id, "uploading", progress={
                    "current_file": fname,
                    "percentage": round(pct, 1),
                    "transferred_bytes": cur,
                    "total_bytes": tot
                })

            _update_fed_job(job_id, "uploading")
            new_version = latest + 1
            _fed_state["filename"] = ""
            _fed_state["bytes"] = 0
            _fed_state["total_bytes"] = 0
            _t0_up = time.time()
            print(
                f"[global-update] ══ Step 5/5 ══ Uploading aggregated model v{new_version} → Azure Blob …",
                flush=True,
            )

            def _up_hb(ver=new_version, t0=_t0_up):
                elapsed = int(time.time() - t0)
                fname = _fed_state["filename"]
                cur   = _fed_state["bytes"]
                tot   = _fed_state["total_bytes"]
                if tot and cur:
                    return (
                        f"[global-update]   Uploading v{ver} → {fname} | "
                        f"{cur/1e9:.2f}/{tot/1e9:.2f} GB ({cur/tot*100:.0f}%) | {elapsed}s elapsed"
                    )
                if fname:
                    return f"[global-update]   Uploading v{ver} → {fname} | {elapsed}s elapsed"
                return f"[global-update]   Uploading aggregated model v{ver} | {elapsed}s elapsed"

            with _PeriodicLogger(10, _up_hb):
                seaweed.upload_hf_model(agg_dir, new_version, progress_callback=_up_progress)
            print(f"[global-update]   HF model upload complete. ({int(time.time()-_t0_up)}s)", flush=True)

            gguf_s3_keys: List[str] = []
            if quant_results:
                try:
                    print(f"[global-update]   Uploading GGUF artifacts for v{new_version} …", flush=True)
                    _fed_state["filename"] = ""
                    _fed_state["bytes"] = 0
                    _fed_state["total_bytes"] = 0
                    with _PeriodicLogger(10, _up_hb):
                        gguf_s3_keys = seaweed.upload_quantized(gguf_dir, new_version, progress_callback=_up_progress)
                    print(f"[global-update]   GGUF(s) uploaded for v{new_version} ✓", flush=True)
                except Exception as exc:
                    print(f"[global-update]   GGUF upload failed (non-fatal): {exc}", flush=True)

            # Register GGUFs in Supabase adapter_registry so Electron devices
            # can discover and download the globally aggregated model.
            if gguf_s3_keys:
                try:
                    from fine_tuning.training_orchestrator import _register_gguf_in_supabase
                    _register_gguf_in_supabase(gguf_s3_keys, new_version, gguf_dir)
                except Exception as exc:
                    print(f"[federated] adapter_registry registration failed (non-fatal): {exc}")

            # ── Mark input versions as consumed so future Global Updates skip them ──
            # Without this, every subsequent run re-aggregates the same input versions
            # because quantized/v{input}/ has no .gguf (the output was v{new_version}).
            for v in downloaded_versions:
                try:
                    seaweed.mark_version_consumed(v, new_version)
                except Exception as _mark_exc:
                    print(f"[global-update]   Warning: could not mark v{v} consumed: {_mark_exc}")

            # ── Done ──────────────────────────────────────────────────────────
            _set_fed_job(job_id, {
                **_fed_jobs.get(job_id, {}),
                "status": "completed",
                "phase": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "version": new_version,
                "versions_aggregated": downloaded_versions,
                "versions_skipped": skipped_versions,
            })
            print(
                f"[global-update] ✓ Global Update complete — "
                f"aggregated model v{new_version} is now live in Azure Blob.",
                flush=True,
            )
        finally:
            _shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as exc:
        import traceback
        print(f"[federated] Job {job_id} FAILED: {exc}\n{traceback.format_exc()[-1000:]}")
        with _fed_jobs_lock:
            if job_id in _fed_jobs:
                _fed_jobs[job_id].update({
                    "status": "failed",
                    "phase": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                })


def _run_share_job(job_id: str, pending_entries: List[tuple]) -> None:
    """
    Background thread: upload all pending weight versions to storage (Azure Blob / SeaweedFS).
    pending_entries: list of (file_path: Path, pending: Dict) tuples, one per training run.
    Processes sequentially. Deletes each file after successful upload.
    Stops on first failure (undeleted file stays for retry).
    """
    def _upd(phase: str, **kw: Any) -> None:
        with _share_jobs_lock:
            if job_id in _share_jobs:
                _share_jobs[job_id]["phase"] = phase
                _share_jobs[job_id].update(kw)

    # Shared state dict read by the periodic heartbeat thread
    _state: Dict[str, Any] = {"filename": "", "bytes": 0, "total_bytes": 0}

    def _progress_cb(filename: str, current: int, total: Optional[int]) -> None:
        pct = (current / total * 100) if total else 0
        _state["filename"] = filename
        _state["bytes"] = current
        _state["total_bytes"] = total or 0
        with _share_jobs_lock:
            if job_id in _share_jobs:
                _share_jobs[job_id]["progress"] = {
                    "current_file": filename,
                    "percentage": round(pct, 1),
                    "transferred_bytes": current,
                    "total_bytes": total,
                }

    try:
        from fine_tuning.training_orchestrator import promote_adapter
        import shutil as _shutil

        uploaded_versions: List[int] = []
        failed_versions: List[tuple] = []   # (version, error_str)
        total_versions = len(pending_entries)

        for idx, (file_path, pending) in enumerate(pending_entries, 1):
            version = pending.get("version", "?")
            _upd(f"uploading_v{version}", current_version=version)
            print(
                f"[share-gradients] ══ Version {idx}/{total_versions} ══ "
                f"Starting upload for v{version} …",
                flush=True,
            )
            _state["filename"] = ""
            _state["bytes"] = 0
            _state["total_bytes"] = 0

            try:
                # Validate paths exist before calling promote_adapter
                merged_model_path = pending.get("merged_model_path", "")
                adapter_path = pending.get("adapter_path", "")
                if not merged_model_path or not Path(merged_model_path).exists():
                    raise RuntimeError(
                        f"merged_model_path missing or not on disk: '{merged_model_path}'. "
                        "The pod may have restarted and lost the merged weights."
                    )
                if not adapter_path or not Path(adapter_path).exists():
                    raise RuntimeError(
                        f"adapter_path missing or not on disk: '{adapter_path}'."
                    )

                _t0_ver = time.time()

                def _heartbeat(ver=version, t0=_t0_ver):
                    elapsed = int(time.time() - t0)
                    fname = _state["filename"]
                    cur   = _state["bytes"]
                    tot   = _state["total_bytes"]
                    if tot and cur:
                        gb_cur = cur / 1e9
                        gb_tot = tot / 1e9
                        pct    = cur / tot * 100
                        return (
                            f"[share-gradients] Uploading v{ver} → {fname} | "
                            f"{gb_cur:.2f}/{gb_tot:.2f} GB ({pct:.0f}%) | {elapsed}s elapsed"
                        )
                    if fname:
                        return f"[share-gradients] Processing v{ver} → {fname} | {elapsed}s elapsed"
                    return f"[share-gradients] Uploading v{ver} to Azure Blob | {elapsed}s elapsed"

                print(
                    f"[share-gradients] Step 1/3 — Uploading merged model + running quantization …",
                    flush=True,
                )
                with _PeriodicLogger(10, _heartbeat):
                    promote_adapter(
                        adapter_id=pending["job_id"],
                        registry_path=pending["registry_path"],
                        version=pending["version"],
                        merged_model_path=pending["merged_model_path"],
                        adapter_path=pending["adapter_path"],
                        eval_scores=pending.get("eval_scores", {}),
                        training_meta=pending.get("training_meta", {}),
                        base_model=pending.get("base_model", ""),
                        progress_callback=_progress_cb,
                        skip_quantization=True,  # raw weights only — Global Update quantizes after FedAvg
                    )
                print(
                    f"[share-gradients] Step 2/3 — Upload complete ({int(time.time()-_t0_ver)}s). "
                    f"Removing local copies …",
                    flush=True,
                )

                # Delete pending-share manifest only after confirmed upload success
                file_path.unlink(missing_ok=True)

                # Delete local weight directories — they are now safely in storage
                _merged = Path(merged_model_path)
                if _merged.exists():
                    _shutil.rmtree(_merged, ignore_errors=True)
                    print(f"[share-gradients]   Deleted local merged model: {_merged}", flush=True)
                # GGUF dir sits next to the merged dir as {version}-gguf/
                _gguf_dir = _merged.parent / f"{version}-gguf"
                if _gguf_dir.exists():
                    _shutil.rmtree(_gguf_dir, ignore_errors=True)
                    print(f"[share-gradients]   Deleted local GGUF dir: {_gguf_dir}", flush=True)
                _adapter = Path(adapter_path)
                if _adapter.exists():
                    _shutil.rmtree(_adapter, ignore_errors=True)
                    print(f"[share-gradients]   Deleted local adapter: {_adapter}", flush=True)

                uploaded_versions.append(version)
                print(
                    f"[share-gradients] Step 3/3 — v{version} ✓ Weights shared and local copies cleared.",
                    flush=True,
                )

            except Exception as ver_exc:
                import traceback as _tb
                print(
                    f"[share-gradients] v{version} FAILED (continuing with remaining versions): "
                    f"{ver_exc}\n{_tb.format_exc()[-600:]}"
                )
                failed_versions.append((version, str(ver_exc)))

        final_status = "completed" if not failed_versions else (
            "partial" if uploaded_versions else "failed"
        )
        with _share_jobs_lock:
            _share_jobs[job_id].update({
                "status":            final_status,
                "phase":             "done",
                "finished_at":       datetime.now(timezone.utc).isoformat(),
                "uploaded_versions": uploaded_versions,
                "failed_versions":   [str(v) for v, _ in failed_versions],
                "version":           uploaded_versions[-1] if uploaded_versions else None,
            })
        if failed_versions:
            print(
                f"[share-gradients] Done — uploaded: {uploaded_versions}, "
                f"failed: {[v for v, _ in failed_versions]}"
            )
        else:
            print(f"[share-gradients] All done — uploaded: {uploaded_versions}")

    except Exception as exc:
        import traceback
        print(f"[share-gradients] FAILED: {exc}\n{traceback.format_exc()[-1000:]}")
        with _share_jobs_lock:
            if job_id in _share_jobs:
                _share_jobs[job_id].update({
                    "status":      "failed",
                    "phase":       "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error":       str(exc),
                })


@app.post("/share-gradients")
async def share_gradients_endpoint(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """
    Upload ALL locally-merged fine-tuned weight versions to storage (Azure Blob / SeaweedFS).
    Must be called manually by the user after Local Training completes.
    Reads every *.json file from /workspace/fine_tuning/pending_shares/ written by job_runner.
    Each version gets its own file — none are overwritten, all are uploaded.
    """
    import asyncio

    if not PENDING_SHARE_DIR.exists():
        return {
            "status":  "no_pending",
            "message": "No weights ready to share. Complete Local Training first.",
        }

    def _version_key(p: Path) -> int:
        try:
            return int(p.stem.lstrip("v"))
        except ValueError:
            return 0

    pending_files = sorted(PENDING_SHARE_DIR.glob("*.json"), key=_version_key)
    if not pending_files:
        return {
            "status":  "no_pending",
            "message": "No weights ready to share. Complete Local Training first.",
        }

    pending_entries: List[tuple] = []
    for fp in pending_files:
        try:
            pending_entries.append((fp, json.loads(fp.read_text(encoding="utf-8"))))
        except Exception as exc:
            print(f"[share-gradients] Skipping unreadable file {fp.name}: {exc}")

    if not pending_entries:
        return {"status": "error", "message": "Pending share files exist but could not be read."}

    versions = [p.get("version") for _, p in pending_entries]
    job_id = str(uuid.uuid4())
    with _share_jobs_lock:
        _share_jobs[job_id] = {
            "job_id":            job_id,
            "status":            "running",
            "phase":             "starting",
            "started_at":        datetime.now(timezone.utc).isoformat(),
            "finished_at":       None,
            "pending_versions":  versions,
            "uploaded_versions": [],
            "error":             None,
            "progress":          None,
        }

    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _run_share_job, job_id, pending_entries)

    return {
        "status":           "queued",
        "job_id":           job_id,
        "pending_versions": versions,
        "message": (
            f"Uploading {len(pending_entries)} version(s) {versions} to storage. "
            f"Poll GET /share-gradients/jobs/{job_id}."
        ),
    }


@app.get("/share-gradients/status")
def share_gradients_status() -> Dict[str, Any]:
    """Return whether there are pending weights ready to share."""
    if not PENDING_SHARE_DIR.exists():
        return {"has_pending": False, "pending_count": 0, "pending_versions": []}

    def _version_key(p: Path) -> int:
        try:
            return int(p.stem.lstrip("v"))
        except ValueError:
            return 0

    pending_files = sorted(PENDING_SHARE_DIR.glob("*.json"), key=_version_key)
    pending_versions: List[int] = []
    for fp in pending_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            v = data.get("version")
            if v is not None:
                pending_versions.append(v)
        except Exception:
            pass

    return {
        "has_pending":      len(pending_files) > 0,
        "pending_count":    len(pending_files),
        "pending_versions": pending_versions,
    }


@app.get("/share-gradients/jobs/{job_id}")
def get_share_gradients_job(job_id: str) -> Dict[str, Any]:
    """Poll the status of a share-gradients job."""
    with _share_jobs_lock:
        job = _share_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Share-gradients job '{job_id}' not found")
    return job


@app.post("/federated/start")
async def start_federated(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """
    Collect all fine-tuned weight versions from SeaweedFS and run FedAvg aggregation.
    Returns immediately with job_id; poll GET /federated/jobs/{job_id} for status.
    """
    import asyncio
    from fine_tuning.storage_client import get_storage_client

    seaweed = get_storage_client()

    # ── Pre-flight: verify storage is reachable before queuing the job ───────
    if not seaweed._configured:
        return {
            "status": "error",
            "message": "Storage backend is not configured on the pod. "
                       "Set STORAGE_BACKEND=azure + AZURE_BLOB_* vars, "
                       "or STORAGE_BACKEND=seaweedfs + SEAWEEDFS_ENDPOINT.",
        }

    loop = asyncio.get_event_loop()
    try:
        # Run probe() off the event loop so it never blocks incoming requests.
        # Hard 15s timeout prevents Cloudflare 524 if Azure is slow/unreachable.
        await asyncio.wait_for(loop.run_in_executor(None, seaweed.probe), timeout=15.0)
    except asyncio.TimeoutError:
        return {
            "status": "storage_unreachable",
            "message": f"Storage probe timed out after 15s at {seaweed._endpoint}.",
        }
    except Exception as _conn_exc:
        return {
            "status": "storage_unreachable",
            "message": (
                f"Cannot reach storage at {seaweed._endpoint} (container/bucket={seaweed._bucket}). "
                f"Error: {_conn_exc}."
            ),
        }

    latest = await loop.run_in_executor(None, seaweed.get_latest_finetuned_version)
    if latest is None:
        return {
            "status": "no_weights",
            "message": "No fine-tuned weights found in storage. Complete Local Training first.",
            "versions_found": 0,
        }

    job_id = str(uuid.uuid4())
    _set_fed_job(job_id, {
        "job_id": job_id,
        "status": "running",
        "phase": "starting",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
        "version": None,
        "versions_aggregated": [],
        "progress": None,
    })

    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _run_federated_job, job_id)

    return {
        "status": "queued",
        "job_id": job_id,
        "message": f"Federated aggregation started. Poll GET /federated/jobs/{job_id} for progress.",
    }


@app.get("/federated/jobs/{job_id}")
def get_federated_job(job_id: str) -> Dict[str, Any]:
    """Return current status of a federated aggregation job."""
    with _fed_jobs_lock:
        job = _fed_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Federated job '{job_id}' not found")
    return job


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
