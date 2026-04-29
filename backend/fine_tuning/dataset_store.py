"""
SQLite-backed local storage for fine-tuning training datasets.

Stores every training example used in a job for reproducibility and auditing.
Path is controlled by FT_DATASET_DB_PATH (defaults to fine_tuning/training_datasets.db).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "training_datasets.db"


def _db_path() -> Path:
    import os
    p = os.getenv("FT_DATASET_DB_PATH", "").strip()
    return Path(p) if p else _DEFAULT_DB


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create tables if they do not exist."""
    db = db_path or _db_path()
    with _connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS training_jobs (
                job_id       TEXT PRIMARY KEY,
                run_id       TEXT,
                pod_id       TEXT,
                domain       TEXT NOT NULL DEFAULT 'acord',
                record_count INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS training_examples (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id        TEXT NOT NULL,
                seq           INTEGER NOT NULL DEFAULT 0,
                split         TEXT NOT NULL DEFAULT 'train',
                instruction   TEXT,
                input         TEXT,
                output        TEXT,
                category      TEXT,
                metadata_json TEXT,
                created_at    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ex_job    ON training_examples(job_id);
            CREATE INDEX IF NOT EXISTS idx_ex_split  ON training_examples(job_id, split);
            CREATE INDEX IF NOT EXISTS idx_ex_cat    ON training_examples(category);
            """
        )


def store_dataset(
    job_id: str,
    run_id: str | None,
    pod_id: str | None,
    domain: str,
    rows: list[dict],
    *,
    split: str = "train",
    db_path: Path | None = None,
) -> int:
    """
    Persist training rows to SQLite.

    Idempotent: re-running with the same job_id + split replaces existing rows.
    Returns the number of rows stored.
    """
    if not rows:
        return 0

    db = db_path or _db_path()
    init_db(db)
    now = datetime.now(timezone.utc).isoformat()

    with _connect(db) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO training_jobs "
            "(job_id, run_id, pod_id, domain, record_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, run_id, pod_id, domain, 0, now),
        )
        # Remove any prior examples for this job+split (handles reruns)
        conn.execute(
            "DELETE FROM training_examples WHERE job_id=? AND split=?",
            (job_id, split),
        )
        conn.executemany(
            "INSERT INTO training_examples "
            "(job_id, seq, split, instruction, input, output, category, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    job_id,
                    i,
                    split,
                    r.get("instruction"),
                    r.get("input"),
                    r.get("output"),
                    (r.get("metadata") or {}).get("category"),
                    json.dumps(r.get("metadata") or {}, ensure_ascii=False),
                    now,
                )
                for i, r in enumerate(rows)
            ],
        )
        # Keep record_count accurate (total across all splits for this job)
        conn.execute(
            "UPDATE training_jobs SET record_count = "
            "(SELECT COUNT(*) FROM training_examples WHERE job_id=?) "
            "WHERE job_id=?",
            (job_id, job_id),
        )

    return len(rows)


def get_dataset(
    job_id: str,
    *,
    split: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    """Retrieve stored training examples for a job, optionally filtered by split."""
    db = db_path or _db_path()
    if not db.exists():
        return []

    with _connect(db) as conn:
        if split:
            cur = conn.execute(
                "SELECT seq, split, instruction, input, output, category, metadata_json "
                "FROM training_examples WHERE job_id=? AND split=? ORDER BY seq",
                (job_id, split),
            )
        else:
            cur = conn.execute(
                "SELECT seq, split, instruction, input, output, category, metadata_json "
                "FROM training_examples WHERE job_id=? ORDER BY split, seq",
                (job_id,),
            )
        rows = []
        for seq, spl, instruction, inp, out, cat, meta_json in cur.fetchall():
            rows.append(
                {
                    "seq": seq,
                    "split": spl,
                    "instruction": instruction,
                    "input": inp,
                    "output": out,
                    "category": cat,
                    "metadata": json.loads(meta_json) if meta_json else {},
                }
            )
        return rows


def list_jobs(
    domain: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict]:
    """List recent training jobs stored in SQLite."""
    db = db_path or _db_path()
    if not db.exists():
        return []

    with _connect(db) as conn:
        if domain:
            cur = conn.execute(
                "SELECT job_id, run_id, pod_id, domain, record_count, created_at "
                "FROM training_jobs WHERE domain=? ORDER BY created_at DESC LIMIT ?",
                (domain, limit),
            )
        else:
            cur = conn.execute(
                "SELECT job_id, run_id, pod_id, domain, record_count, created_at "
                "FROM training_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        cols = ["job_id", "run_id", "pod_id", "domain", "record_count", "created_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
