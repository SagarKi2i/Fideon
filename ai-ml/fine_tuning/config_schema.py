"""
Load and validate the fine-tuning pipeline config (fine_tuning/config.yaml).
Resolves ${ENV_VAR:-default} placeholders before returning.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml


_ENV_RE = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")


def _resolve(value: str) -> str:
    def _sub(m: re.Match) -> str:
        var, default = m.group(1), m.group(2) or ""
        return os.environ.get(var, default)
    return _ENV_RE.sub(_sub, value)


def _walk_resolve(obj: Any) -> Any:
    if isinstance(obj, str):
        return _resolve(obj)
    if isinstance(obj, dict):
        return {k: _walk_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_resolve(i) for i in obj]
    return obj


def load_and_validate_config(config_path: str) -> Dict[str, Any]:
    """
    Load config.yaml, resolve env-var placeholders, and return as a plain dict.
    Raises FileNotFoundError / ValueError on missing / invalid config.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Fine-tuning config not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg: Dict[str, Any] = _walk_resolve(raw)

    base_model = (cfg.get("base_model") or "").strip()
    if not base_model:
        raise ValueError("config.yaml: 'base_model' is required")

    local_only = str(cfg.get("local_files_only", "false")).lower() in {"1", "true", "yes"}
    if local_only:
        p = Path(base_model)
        if not p.exists():
            raise FileNotFoundError(
                f"local_files_only=true but base_model path missing: {base_model}"
            )

    paths = cfg.setdefault("paths", {})
    paths.setdefault("datasets_dir",  "/workspace/fine_tuning/datasets")
    paths.setdefault("runs_dir",      "/workspace/fine_tuning/runs")
    paths.setdefault("registry_path", "/workspace/fine_tuning/registry/version_registry.json")

    cl = cfg.setdefault("continuous_learning", {})
    cl.setdefault("enabled", True)
    cl.setdefault("retrain_threshold", 25)
    cl.setdefault("feedback_datasets_dir", "/workspace/fine_tuning/datasets/feedback_learning")

    cfg.setdefault("training", {}).setdefault("replay_fraction", 0.30)

    return cfg
