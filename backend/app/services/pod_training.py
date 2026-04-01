from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import os

from app.core.supabase import postgrest_insert


def _backend_root() -> Path:
    # backend/app/services/pod_training.py -> backend/
    return Path(__file__).resolve().parents[2]


def _auto_enabled() -> bool:
    v = (os.getenv("AUTO_FINE_TUNE_ON_POD_APPROVAL") or "true").strip().lower()
    return v in {"1", "true", "yes", "on"}


async def create_job_row(*, pod_id: str, run_id: str, created_by: str | None) -> dict:
    rows = await postgrest_insert(
        "pod_training_jobs",
        {"pod_id": pod_id, "run_id": run_id, "created_by": created_by, "status": "queued"},
    )
    return rows[0]


def spawn_job_runner(*, pod_id: str, job_id: str, run_id: str) -> None:
    """
    Fire-and-forget process that updates Supabase job status/logs.
    """
    if not _auto_enabled():
        return

    backend_dir = _backend_root()
    py = sys.executable
    cmd = [
        py,
        "-m",
        "fine_tuning.job_runner",
        "--job-id",
        job_id,
        "--run-id",
        run_id,
        "--pod-id",
        pod_id,
    ]

    subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

