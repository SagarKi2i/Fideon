"""
DatasetBuilder — assemble a training JSONL for one fine-tuning cycle.

Workflow
--------
1. Load new chat-format rows from new_data_path (the versioned snapshot).
2. Validate each row (must have messages: system/user/assistant).
3. Soft-validate assistant JSON against the schema registry (log only, never reject).
4. Sample replay rows from previous versioned snapshots (anti-forgetting).
5. Stratified interleave — shuffle within each doc type, then interleave
   round-robin so training batches see diverse document types.
6. Compute SHA-256 fingerprint of the combined train set.
7. Write train.jsonl + dataset_manifest.json + dataset_quality_report.json
   to datasets/cycle-{cycle_id}/.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
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
    synthetic_records: int
    rejected_records: int
    cycle_id: str
    quality_report: Dict[str, Any] = dc_field(default_factory=dict)


# ── Assistant content parser (handles FIELDS: format + legacy plain JSON) ────

def parse_assistant_fields(content: str) -> Optional[Dict[str, Any]]:
    """Extract the JSON fields dict from assistant content.

    Handles both formats:
    - New:    FIELDS:\\n{json}\\n\\nRAW TEXT:...\\n\\nMARKDOWN:...
    - Legacy: plain JSON string
    Returns None when no valid JSON object is found.
    """
    if not isinstance(content, str):
        return None
    stripped = content.strip()
    fi = stripped.find("FIELDS:")
    if fi != -1:
        after = stripped[fi + len("FIELDS:"):]
        for end_m in ("RAW TEXT:", "MARKDOWN:"):
            ei = after.find(end_m)
            if ei != -1:
                after = after[:ei]
                break
        s = after.find("{")
        e = after.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(after[s : e + 1])
            except json.JSONDecodeError:
                pass
    # Legacy: bare JSON
    s = stripped.find("{")
    e = stripped.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(stripped[s : e + 1])
        except json.JSONDecodeError:
            pass
    return None


# ── Hard validation (rejects the row) ────────────────────────────────────────

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
        content = m.get("content")
        if isinstance(content, list):
            # Multimodal content (image + text blocks for user/system messages)
            if not content:
                raise InvalidChatFormatError(
                    f"Row {row_index}, message {i}: 'content' list must be non-empty"
                )
        elif not isinstance(content, str) or not content.strip():
            raise InvalidChatFormatError(
                f"Row {row_index}, message {i}: 'content' must be a non-empty string or list"
            )
    # Validate assistant turn contains a parseable JSON fields dict.
    # Accepts both FIELDS: format and legacy plain JSON.
    for m in msgs:
        if m.get("role") == "assistant":
            content = m.get("content", "").strip()
            if parse_assistant_fields(content) is None:
                raise InvalidChatFormatError(
                    f"Row {row_index}: assistant content has no valid JSON fields "
                    f"(expected FIELDS:{{...}} or plain JSON). Got: {content[:100]!r}"
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
        self._cfg   = config
        self._paths = config.get("paths", {})
        self._cl    = config.get("continuous_learning", {})

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _doc_type_of(row: Dict[str, Any]) -> str:
        """Extract document_type from a chat-format row's metadata, with fallback."""
        meta = row.get("metadata") or {}
        return (
            meta.get("document_type")
            or meta.get("form_type")
            or "UNKNOWN"
        )

    @staticmethod
    def _count_fields(obj: Any, _depth: int = 0) -> int:
        """Recursively count leaf fields in a JSON object (max depth 10 to guard cycles)."""
        if _depth > 10 or not isinstance(obj, dict):
            return 0
        count = 0
        for v in obj.values():
            count += 1
            if isinstance(v, dict):
                count += DatasetBuilder._count_fields(v, _depth + 1)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        count += DatasetBuilder._count_fields(item, _depth + 1)
        return count

    def _validate_sample_extended(self, row: Dict[str, Any], row_index: int) -> None:
        """
        Soft-validate assistant JSON against the schema registry.
        Never raises — only prints warnings so a schema mismatch never
        blocks a training cycle.
        """
        assistant_msg = next(
            (m for m in row.get("messages", []) if m.get("role") == "assistant"), None
        )
        if not assistant_msg:
            return
        assistant_json = parse_assistant_fields(assistant_msg.get("content", ""))
        if assistant_json is None:
            print(
                f"[dataset_builder] Row {row_index}: assistant content has no valid "
                "JSON fields — skipping schema validation",
                flush=True,
            )
            return
        try:
            from insurance_schema_registry import get_registry
            validation = get_registry().validate(assistant_json)
            if not validation.get("valid"):
                errs = validation.get("errors", [])
                sample_id = (row.get("metadata") or {}).get("sample_id", f"row-{row_index}")
                print(
                    f"[dataset_builder] Sample {sample_id} schema warning "
                    f"({len(errs)} issue(s)): {errs[:2]}",
                    flush=True,
                )
        except Exception:
            pass  # Registry unavailable — silently skip

    def _generate_quality_report(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute quality metrics for the assembled dataset."""
        doc_types: Dict[str, int] = {}
        field_counts: List[int]   = []

        for row in rows:
            dt = self._doc_type_of(row)
            doc_types[dt] = doc_types.get(dt, 0) + 1
            assistant_msg = next(
                (m for m in row.get("messages", []) if m.get("role") == "assistant"),
                None,
            )
            if assistant_msg:
                fields = parse_assistant_fields(assistant_msg.get("content", ""))
                if fields is not None:
                    field_counts.append(self._count_fields(fields))

        return {
            "total_samples":            len(rows),
            "document_types":           doc_types,
            "document_type_diversity":  len(doc_types),
            "avg_fields_per_sample":    (
                round(sum(field_counts) / len(field_counts), 1)
                if field_counts else 0
            ),
        }

    @staticmethod
    def _stratified_interleave(
        rows: List[Dict[str, Any]],
        seed: int,
    ) -> List[Dict[str, Any]]:
        """
        Shuffle within each document type, then interleave round-robin so
        every training batch sees a variety of document types rather than
        long runs of a single type.
        """
        rng = random.Random(seed)

        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[DatasetBuilder._doc_type_of(row)].append(row)

        for bucket in buckets.values():
            rng.shuffle(bucket)

        # Deterministic key order so the same seed always yields the same result
        sorted_types = sorted(buckets.keys())
        interleaved: List[Dict[str, Any]] = []
        max_len = max(len(b) for b in buckets.values()) if buckets else 0
        for i in range(max_len):
            for dt in sorted_types:
                if i < len(buckets[dt]):
                    interleaved.append(buckets[dt][i])
        return interleaved

    # ── Public method ─────────────────────────────────────────────────────────

    def build(
        self,
        new_data_path: str,
        cycle_id: str,
        min_records: int = 1,
        replay_seed: int = 42,
    ) -> DatasetBuildResult:
        """
        Build a training JSONL for cycle_id.

        Parameters
        ----------
        new_data_path : versioned JSONL snapshot produced by version_store.
        cycle_id      : unique identifier for this training cycle.
        min_records   : raise InsufficientDataError if combined rows < this.
        replay_seed   : RNG seed for interleaving (same seed → same order).
        """
        datasets_dir = Path(
            self._paths.get("datasets_dir", "/workspace/fine_tuning/datasets")
        )
        cycle_dir = datasets_dir / f"cycle-{cycle_id}"
        cycle_dir.mkdir(parents=True, exist_ok=True)

        feedback_dir = self._cl.get(
            "feedback_datasets_dir",
            "/workspace/fine_tuning/datasets/feedback_learning",
        )

        # Minimum samples per doc type below which a warning is printed.
        min_samples_per_type: int = int(
            self._cl.get("min_samples_per_doc_type", 5)
        )

        # ── 1. Load + hard-validate new rows ─────────────────────────────────
        new_rows: List[Dict[str, Any]] = []
        rejected = 0
        for i, row in enumerate(_read_jsonl(Path(new_data_path))):
            try:
                validate_chat_format(row, i)
                new_rows.append(row)
            except InvalidChatFormatError:
                rejected += 1
                print(
                    f"[dataset_builder] Row {i} rejected (invalid chat format)"
                    " — check ingest pipeline",
                    flush=True,
                )

        # ── 2. Soft-validate new rows against schema registry ─────────────────
        for i, row in enumerate(new_rows):
            self._validate_sample_extended(row, i)

        # ── 3. 70/20/10 composition: 70% new, ~20% replay, ~10% synthetic ───────
        n_new    = len(new_rows)
        n_replay = round(n_new * 2 / 7)   # ≈ 20%
        n_synth  = round(n_new * 1 / 7)   # ≈ 10%

        sampler     = ReplaySampler(feedback_dir)
        replay_rows = sampler.sample(n_replay, seed=replay_seed)
        print(
            f"[dataset_builder] 70/20/10: {n_new} new + "
            f"{len(replay_rows)}/{n_replay} replay target",
            flush=True,
        )

        from fine_tuning.dataset.augmentor import DataAugmentor, AugmentorConfig as _AugCfg
        _augmentor  = DataAugmentor(_AugCfg(copies_per_sample=1, seed=replay_seed))
        _all_synth  = _augmentor.augment_dataset(new_rows, n_copies=1)
        _rng        = random.Random(replay_seed)
        synthetic_rows: List[Dict[str, Any]] = (
            _rng.sample(_all_synth, min(n_synth, len(_all_synth)))
            if _all_synth else []
        )
        print(
            f"[dataset_builder] Synthetic rows: {len(synthetic_rows)}/{n_synth} target",
            flush=True,
        )

        # ── 4. Combine + stratified interleave ────────────────────────────────
        combined = new_rows + replay_rows + synthetic_rows
        final    = self._stratified_interleave(combined, seed=replay_seed)

        if len(final) < min_records:
            raise InsufficientDataError(
                f"Only {len(final)} valid training records "
                f"(need ≥{min_records}). Collect more corrections."
            )

        # ── 5. Document-type distribution + low-count warnings ───────────────
        doc_type_counts: Dict[str, int] = {}
        for row in final:
            dt = self._doc_type_of(row)
            doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1

        for dt, count in doc_type_counts.items():
            if count < min_samples_per_type:
                print(
                    f"[dataset_builder] WARNING: document type '{dt}' has only "
                    f"{count} sample(s) (recommended minimum: {min_samples_per_type})",
                    flush=True,
                )

        # ── 6. Fingerprint + write train.jsonl ────────────────────────────────
        fingerprint = _compute_fingerprint(final)
        train_path  = cycle_dir / "train.jsonl"
        _write_jsonl(train_path, final)
        (cycle_dir / "train.hash").write_text(fingerprint, encoding="utf-8")

        # ── 7. Manifest ───────────────────────────────────────────────────────
        manifest = {
            "cycle_id":                   cycle_id,
            "new_records":                len(new_rows),
            "replay_records":             len(replay_rows),
            "synthetic_records":          len(synthetic_rows),
            "rejected_records":           rejected,
            "total_records":              len(final),
            "document_type_distribution": doc_type_counts,
            "fingerprint":                fingerprint,
            "new_data_path":              new_data_path,
            "created_at":                 datetime.now(timezone.utc).isoformat(),
        }
        (cycle_dir / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # ── 8. Quality report ─────────────────────────────────────────────────
        quality_report = self._generate_quality_report(final)
        (cycle_dir / "dataset_quality_report.json").write_text(
            json.dumps(quality_report, indent=2), encoding="utf-8"
        )
        print(
            f"[dataset_builder] Quality: {quality_report['total_samples']} samples, "
            f"{quality_report['document_type_diversity']} doc type(s), "
            f"avg {quality_report['avg_fields_per_sample']} fields/sample",
            flush=True,
        )

        # ── 9. LLaMA-Factory data/ layout ─────────────────────────────────────
        # LLaMA-Factory expects a data/ subdirectory with dataset_info.json +
        # train.jsonl so its --dataset flag resolves the file correctly.
        lf_data_dir = cycle_dir / "data"
        lf_data_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(lf_data_dir / "train.jsonl", final)
        _lf_dataset_info = {
            "fideon_insurance": {
                "file_name": "train.jsonl",
                "formatting": "sharegpt",
                "columns": {"messages": "messages"},
            }
        }
        (lf_data_dir / "dataset_info.json").write_text(
            json.dumps(_lf_dataset_info, indent=2), encoding="utf-8"
        )
        print(
            f"[dataset_builder] LLaMA-Factory data/ layout written: {lf_data_dir}",
            flush=True,
        )

        return DatasetBuildResult(
            train_jsonl_path=str(train_path),
            fingerprint=fingerprint,
            total_records=len(final),
            new_records=len(new_rows),
            replay_records=len(replay_rows),
            synthetic_records=len(synthetic_rows),
            rejected_records=rejected,
            cycle_id=cycle_id,
            quality_report=quality_report,
        )
