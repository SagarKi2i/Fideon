"""
VersionRegistry — tracks every training cycle and the currently-active model.

Storage: a single JSON file at paths.registry_path
         (default /workspace/fine_tuning/registry/version_registry.json)

Schema
------
{
  "current_version": 2,
  "current_base": "/workspace/fine_tuning/runs/2-<cycle_id>-merged/",
  "versions": [
    {
      "version": 1,
      "cycle_id": "abc123",
      "status": "promoted",           // pending | promoted | failed
      "parent_version": 0,
      "job_id": "...",
      "adapter_path": "...",
      "merged_model_path": "...",
      "seaweedfs_path": null,
      "seaweedfs_sha256": null,
      "eval_scores": {...},
      "training_meta": {...},
      "created_at": "...",
      "promoted_at": "..."
    }
  ]
}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class VersionRegistry:
    def __init__(self, registry_path: str) -> None:
        self._path = Path(registry_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ── Internal I/O ──────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"current_version": 0, "current_base": None, "versions": []}

    def _save(self, data: Dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_current_base(self) -> Optional[str]:
        """Return path to the currently-active (promoted) merged model, or None."""
        data = self._load()
        return data.get("current_base")

    def get_current_version(self) -> int:
        return self._load().get("current_version", 0)

    def create_pending_entry(
        self,
        cycle_id: str,
        job_id: str,
        parent_version: int,
        replay_fraction: float,
        checkpoint_dir: str,
    ) -> int:
        """
        Register a new version as 'pending' before training starts.
        Returns the new version number.
        """
        data = self._load()
        versions: List[Dict[str, Any]] = data.get("versions", [])
        new_version = max((v["version"] for v in versions), default=0) + 1

        versions.append(
            {
                "version": new_version,
                "cycle_id": cycle_id,
                "status": "pending",
                "parent_version": parent_version,
                "job_id": job_id,
                "adapter_path": None,
                "merged_model_path": None,
                "seaweedfs_path": None,
                "seaweedfs_sha256": None,
                "eval_scores": {},
                "training_meta": {
                    "replay_fraction": replay_fraction,
                    "checkpoint_dir": checkpoint_dir,
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "promoted_at": None,
            }
        )
        data["versions"] = versions
        self._save(data)
        return new_version

    def promote_version(
        self,
        version: int,
        merged_model_path: str,
        adapter_path: str,
        eval_scores: Dict[str, Any],
        training_meta: Dict[str, Any],
    ) -> None:
        """
        Mark version as promoted, update current_version and current_base pointers.
        """
        data = self._load()
        versions: List[Dict[str, Any]] = data.get("versions", [])

        for entry in versions:
            if entry["version"] == version:
                entry["status"] = "promoted"
                entry["adapter_path"] = adapter_path
                entry["merged_model_path"] = merged_model_path
                entry["eval_scores"] = eval_scores
                entry["training_meta"].update(training_meta)
                entry["promoted_at"] = datetime.now(timezone.utc).isoformat()
                break
        else:
            # Entry missing — create it
            versions.append(
                {
                    "version": version,
                    "status": "promoted",
                    "adapter_path": adapter_path,
                    "merged_model_path": merged_model_path,
                    "eval_scores": eval_scores,
                    "training_meta": training_meta,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "promoted_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        data["versions"] = versions
        data["current_version"] = version
        data["current_base"] = merged_model_path
        self._save(data)

    def mark_failed(self, version: int, reason: str) -> None:
        data = self._load()
        for entry in data.get("versions", []):
            if entry["version"] == version:
                entry["status"] = "failed"
                entry["training_meta"]["failure_reason"] = reason
                break
        self._save(data)

    def update_seaweedfs(
        self, adapter_id: str, s3_key: str, sha256: str
    ) -> None:
        data = self._load()
        for entry in data.get("versions", []):
            if entry.get("job_id") == adapter_id or entry.get("cycle_id") == adapter_id:
                entry["seaweedfs_path"] = s3_key
                entry["seaweedfs_sha256"] = sha256
                break
        self._save(data)

    def list_versions(self) -> List[Dict[str, Any]]:
        return self._load().get("versions", [])
