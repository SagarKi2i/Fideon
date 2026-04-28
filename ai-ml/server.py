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
# POST /extract/{upload_id}  — full ACORD extraction (Surya + Docling + Qwen VL)
# ---------------------------------------------------------------------------
@app.post("/extract/{upload_id}")
async def extract_acord(
    upload_id: str,
    form_type_hint: str = "25",
) -> Dict[str, Any]:
    """
    Full ACORD extraction pipeline for an already-uploaded PDF.

    Step 1 (parallel): Surya OCR + Docling run concurrently.
    Step 2 (serial):   Qwen2-VL receives page images + both outputs.

    Returns: { form_type_detected, pdf_type, extracted_json, full_text, markdown }
    Long-running (30s–5min on GPU).
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

    import asyncio
    loop = asyncio.get_running_loop()

    from extractor import run_full_extraction

    result = await loop.run_in_executor(_executor, run_full_extraction, pdf_path, ft)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


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
    max_new_tokens: int = int(body.get("max_new_tokens", 512))
    temperature: float = float(body.get("temperature", 0.3))

    if not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    def _infer() -> str:
        from extractor import _load_qwen, _qwen_model, _qwen_processor
        import torch

        _load_qwen()

        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        text_input = _qwen_processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _qwen_processor(
            text=[text_input],
            padding=True,
            return_tensors="pt",
        ).to(_qwen_model.device)

        with torch.no_grad():
            generated_ids = _qwen_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        return _qwen_processor.batch_decode(
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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
