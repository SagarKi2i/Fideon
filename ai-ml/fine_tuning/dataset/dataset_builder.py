"""
DatasetBuilder — assemble a training JSONL for one fine-tuning cycle.

Workflow
--------
1. Load new chat-format rows from new_data_path (the versioned snapshot).
2. Validate each row (must have messages: system/user/assistant).
3. Sample replay rows from previous versioned snapshots (anti-forgetting).
4. Compute SHA-256 fingerprint of the combined train set.
5. Write train.jsonl + dataset_manifest.json to datasets/cycle-{cycle_id}/.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class InsufficientDataError(RuntimeError):
    pass


class InvalidChatFormatError(ValueError):
    pass


@dataclass
class DatasetBuildResult:
    train_jsonl_path: str
    fingerprint: str
    total_records: int
    new_records: int
    replay_records: int
    rejected_records: int
    cycle_id: str


# ── Validation ────────────────────────────────────────────────────────────────

def validate_chat_format(row: Dict[str, Any], row_index: int) -> None:
    """Raise InvalidChatFormatError if row is not a valid chat sample."""
    msgs = row.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 2:
        raise InvalidChatFormatError(
            f"Row {row_index}: 'messages' must be a list with ≥2 entries"
        )
    roles = [m.get("role") for m in msgs]
    if "assistant" not in roles:
        raise InvalidChatFormatError(
            f"Row {row_index}: 'messages' must contain an 'assistant' turn"
        )
    for i, m in enumerate(msgs):
        if not isinstance(m.get("content"), str) or not m["content"].strip():
            raise InvalidChatFormatError(
                f"Row {row_index}, message {i}: 'content' must be a non-empty string"
            )


# ── JSONL I/O ─────────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s:
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _compute_fingerprint(rows: List[Dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()


# ── Replay sampler ────────────────────────────────────────────────────────────

class ReplaySampler:
    """Load rows from all previous versioned JSONL snapshots for anti-forgetting replay."""

    def __init__(self, feedback_datasets_dir: str) -> None:
        self._root = Path(feedback_datasets_dir)

    def _all_versioned_rows(self) -> List[Dict[str, Any]]:
        versions_dir = self._root / "versions"
        if not versions_dir.exists():
            return []
        all_rows: List[Dict[str, Any]] = []
        for vf in sorted(versions_dir.glob("v*.jsonl")):
            all_rows.extend(_read_jsonl(vf))
        return all_rows

    def sample_all(self) -> List[Dict[str, Any]]:
        """Return ALL rows from all versioned snapshots — no cap."""
        return self._all_versioned_rows()

    def sample(self, n: int, seed: int = 42) -> List[Dict[str, Any]]:
        """Return up to *n* rows sampled uniformly from all versioned snapshots."""
        if n <= 0:
            return []
        all_rows = self._all_versioned_rows()
        if not all_rows:
            return []
        rng = random.Random(seed)
        return rng.sample(all_rows, min(n, len(all_rows)))


# ── Main builder ──────────────────────────────────────────────────────────────

class DatasetBuilder:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config
        self._paths = config.get("paths", {})
        self._cl = config.get("continuous_learning", {})

    def build(
        self,
        new_data_path: str,
        cycle_id: str,
        min_records: int = 1,
        replay_seed: int = 42,
    ) -> DatasetBuildResult:
        """
        Build a training JSONL for cycle_id.
        new_data_path: versioned JSONL snapshot (from version_store).
        """
        datasets_dir = Path(self._paths.get("datasets_dir", "/workspace/fine_tuning/datasets"))
        cycle_dir = datasets_dir / f"cycle-{cycle_id}"
        cycle_dir.mkdir(parents=True, exist_ok=True)

        feedback_dir = self._cl.get(
            "feedback_datasets_dir",
            "/workspace/fine_tuning/datasets/feedback_learning",
        )

        # 1. Load new rows — ALL of them; rejected ones are logged but not skipped silently
        new_rows: List[Dict[str, Any]] = []
        rejected = 0
        for i, row in enumerate(_read_jsonl(Path(new_data_path))):
            try:
                validate_chat_format(row, i)
                new_rows.append(row)
            except InvalidChatFormatError:
                rejected += 1
                print(f"[dataset_builder] Row {i} rejected (invalid chat format) — check ingest pipeline")

        # 2. Replay ALL rows from previous versioned snapshots (no cap) so that no
        #    historical sample is ever excluded from training.
        sampler = ReplaySampler(feedback_dir)
        replay_rows = sampler.sample_all()
        print(f"[dataset_builder] Replay: {len(replay_rows)} historical sample(s) from previous versions")

        # 3. Combine and shuffle
        combined = new_rows + replay_rows
        random.Random(replay_seed).shuffle(combined)

        if len(combined) < min_records:
            raise InsufficientDataError(
                f"Only {len(combined)} valid training records "
                f"(need ≥{min_records}). Collect more corrections."
            )

        # 4. Fingerprint + write
        fingerprint = _compute_fingerprint(combined)
        train_path = cycle_dir / "train.jsonl"
        _write_jsonl(train_path, combined)
        (cycle_dir / "train.hash").write_text(fingerprint, encoding="utf-8")

        manifest = {
            "cycle_id": cycle_id,
            "new_records": len(new_rows),
            "replay_records": len(replay_rows),
            "rejected_records": rejected,
            "total_records": len(combined),
            "fingerprint": fingerprint,
            "new_data_path": new_data_path,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (cycle_dir / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        return DatasetBuildResult(
            train_jsonl_path=str(train_path),
            fingerprint=fingerprint,
            total_records=len(combined),
            new_records=len(new_rows),
            replay_records=len(replay_rows),
            rejected_records=rejected,
            cycle_id=cycle_id,
        )
