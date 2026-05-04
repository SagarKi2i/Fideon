"""
Versioned JSONL store for continuous-learning corrections.

Layout under <root>/ (default /workspace/fine_tuning/datasets/feedback_learning/):
  pending.jsonl             — accumulates new samples until threshold
  versions/v0001.jsonl      — snapshot promoted when threshold crossed
  versions/v0002.jsonl      — next snapshot, etc.
  manifest.json             — { next_version, pending_count, snapshots: [...] }
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── File-based lock ────────────────────────────────────────────────────────────

class RegistryLock:
    """Advisory POSIX file lock around the manifest to prevent concurrent writes."""

    def __init__(self, root: Path, timeout_seconds: int = 30) -> None:
        self._lock_path = root / ".registry.lock"
        self._timeout = timeout_seconds
        self._fh = None

    def __enter__(self) -> "RegistryLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._lock_path, "w", encoding="utf-8")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._fh.close()
                    raise TimeoutError(
                        f"Could not acquire registry lock within {self._timeout}s"
                    )
                time.sleep(0.25)

    def __exit__(self, *_: Any) -> None:
        if self._fh:
            try:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class AppendOutcome:
    pending_count_after: int
    version_snapshot_path: Optional[str] = None
    snapshot_version: Optional[int] = None


# ── Manifest helpers ───────────────────────────────────────────────────────────

def _load_manifest(root: Path) -> Dict[str, Any]:
    mf = root / "manifest.json"
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_version": 1, "pending_count": 0, "snapshots": []}


def _save_manifest(root: Path, manifest: Dict[str, Any]) -> None:
    mf = root / "manifest.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _pending_path(root: Path) -> Path:
    return root / "pending.jsonl"


def _version_path(root: Path, version: int) -> Path:
    return root / "versions" / f"v{version:04d}.jsonl"


# ── Core function ──────────────────────────────────────────────────────────────

def append_training_sample(
    root: Path,
    row: Dict[str, Any],
    retrain_threshold: int = 25,
    lock_timeout: int = 30,
) -> AppendOutcome:
    """
    Append one chat-format training sample to pending.jsonl.

    If pending_count reaches retrain_threshold after the append:
      • pending.jsonl is moved to versions/v{N:04d}.jsonl
      • pending.jsonl is reset to empty
      • manifest.json is updated

    Returns AppendOutcome with snapshot_version set when threshold is crossed.
    """
    root.mkdir(parents=True, exist_ok=True)

    with RegistryLock(root, timeout_seconds=lock_timeout):
        manifest = _load_manifest(root)

        # Append to pending
        pending = _pending_path(root)
        with pending.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        manifest["pending_count"] = manifest.get("pending_count", 0) + 1
        pending_count = manifest["pending_count"]

        snapshot_path: Optional[str] = None
        snapshot_version: Optional[int] = None

        if pending_count >= retrain_threshold:
            version = int(manifest.get("next_version", 1))
            vp = _version_path(root, version)
            vp.parent.mkdir(parents=True, exist_ok=True)

            # Copy pending → versioned snapshot
            vp.write_bytes(pending.read_bytes())

            # Reset pending
            pending.write_text("", encoding="utf-8")
            manifest["pending_count"] = 0
            manifest["next_version"] = version + 1
            manifest.setdefault("snapshots", []).append(
                {
                    "version": version,
                    "path": str(vp),
                    "rows": pending_count,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            snapshot_path = str(vp)
            snapshot_version = version

        _save_manifest(root, manifest)

    return AppendOutcome(
        pending_count_after=manifest["pending_count"],
        version_snapshot_path=snapshot_path,
        snapshot_version=snapshot_version,
    )


def load_pending_rows(root: Path) -> List[Dict[str, Any]]:
    """Return all rows currently in pending.jsonl."""
    p = _pending_path(root)
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            try:
                rows.append(json.loads(s))
            except Exception:
                continue
    return rows


def load_all_versioned_rows(root: Path) -> List[Dict[str, Any]]:
    """Return all rows across all versioned JSONL snapshots (for replay)."""
    versions_dir = root / "versions"
    if not versions_dir.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for vf in sorted(versions_dir.glob("v*.jsonl")):
        for line in vf.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s:
                try:
                    rows.append(json.loads(s))
                except Exception:
                    continue
    return rows
