"""
Fine-tuning job runner for the Fideon RunPod pod.

run_cycle() is the top-level entry point called by server.py when a user
clicks "Fine-tune" or when the correction threshold is crossed automatically.

Full pipeline (mirrors the ACORD pipeline document STEP 6):

  load_and_validate_config()
      ↓
  check_eval_files()          — pre-flight (non-fatal)
      ↓
  RegistryLock                — prevent concurrent cycles
      ↓
  DatasetBuilder.build()      — new JSONL + replay rows → train.jsonl
      ↓
  resolve_base_model_path()   — SeaweedFS latest → registry → base model
      ↓
  registry.create_pending_entry()
      ↓
  run_training()              — QLoRA SFT → LoRA adapter
      ↓
  run_local_eval()            — field F1/recall on eval examples
      ↓
  run_deepeval()              — optional LLM-judge metrics
      ↓
  ForgettingEvaluator.evaluate()
      ↓
  run_eval_gate()             — promote / block decision
      ↓
  [gate passed]
  AdapterMerger.merge()       — merge adapter → full weights
      ↓
  promote_adapter()           — SeaweedFS upload + registry + model card + alert
      ↓
  registry.promote_version()  — SLM v1.N is now the active model
"""
from __future__ import annotations

import json
import os
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CycleResult:
    status: str                     # "completed" | "failed" | "gate_failed"
    cycle_id: str
    version: Optional[int]
    adapter_path: Optional[str]
    merged_model_path: Optional[str]
    gate_passed: bool
    eval_scores: Dict[str, Any]
    error: Optional[str]
    started_at: str
    finished_at: str


# ── In-memory job store (server.py reads this for status polling) ─────────────

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    with _jobs_lock:
        return _jobs.get(job_id)


def _set_job(job_id: str, data: Dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[job_id] = data


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_eval_files(config: Dict[str, Any]) -> None:
    """Warn (non-fatal) if eval JSON files referenced in config are missing."""
    eval_cfg = config.get("evaluation", {})
    for key in ("seen_questions_path", "paraphrased_questions_path", "out_of_scope_questions_path"):
        p = eval_cfg.get(key)
        if p and not Path(p).exists():
            print(f"[job_runner] Warning: eval file not found: {p}")


def _load_eval_examples_from_config(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load eval examples from the paths in config.evaluation.
    Returns a list of {"user_content": str, "expected_fields": dict}.
    """
    eval_cfg = config.get("evaluation", {})
    examples: List[Dict[str, Any]] = []

    for path_key in ("seen_questions_path", "paraphrased_questions_path"):
        p = eval_cfg.get(path_key)
        if not p or not Path(p).exists():
            continue
        try:
            raw = json.loads(Path(p).read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else []
            for item in items:
                uc = item.get("user_content") or item.get("input") or item.get("question") or ""
                ef = item.get("expected_fields") or item.get("output") or {}
                if isinstance(ef, str):
                    try:
                        ef = json.loads(ef)
                    except Exception:
                        ef = {}
                examples.append({"user_content": uc, "expected_fields": ef})
        except Exception as exc:
            print(f"[job_runner] Warning: could not load eval file {p}: {exc}")

    return examples


def _resolve_base_model(config: Dict[str, Any], registry_path: str) -> str:
    """
    Return the base model path to train from, in priority order:

      1. Latest fine-tuned model on SeaweedFS (finetuned/v{N}/)
         — downloaded to /workspace/fine_tuning/models/finetuned/v{N}/ if not cached
      2. Current promoted model path from local registry (already on disk)
      3. config.base_model (original Qwen2-VL-7B)

    This implements the continuous-learning loop: each cycle fine-tunes on top
    of the previously promoted model rather than the original base weights.
    """
    from fine_tuning.seaweedfs_client import SeaweedFSClient
    from fine_tuning.registry.version_registry import VersionRegistry

    seaweed = SeaweedFSClient()

    # ── 1. SeaweedFS: latest fine-tuned version ───────────────────────────────
    seaweed_version = seaweed.get_latest_finetuned_version()
    if seaweed_version is not None:
        cache_dir = f"/workspace/fine_tuning/models/finetuned/v{seaweed_version}"
        # Check if already cached locally (avoid re-download on every cycle)
        cache_path = Path(cache_dir)
        if cache_path.exists() and any(cache_path.iterdir()):
            print(
                f"[job_runner] Using cached SeaweedFS model v{seaweed_version}: {cache_dir}"
            )
            return cache_dir
        # Not cached — download from SeaweedFS
        print(
            f"[job_runner] Downloading fine-tuned model v{seaweed_version} "
            f"from SeaweedFS → {cache_dir} …"
        )
        try:
            seaweed.download_finetuned_model(seaweed_version, cache_dir)
            print(f"[job_runner] SeaweedFS model v{seaweed_version} ready at {cache_dir}")
            return cache_dir
        except Exception as exc:
            print(f"[job_runner] SeaweedFS download failed (non-fatal): {exc}")

    # ── 2. Local registry: last promoted path ─────────────────────────────────
    registry = VersionRegistry(registry_path)
    current = registry.get_current_base()
    if current and Path(current).exists():
        print(f"[job_runner] Resuming from local promoted model: {current}")
        return current

    # ── 3. Original base model ────────────────────────────────────────────────
    fallback = config.get("base_model", "/workspace/models/qwen2-vl-7b")
    print(f"[job_runner] Using original base model: {fallback}")
    return fallback


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_cycle(
    config_path: str,
    new_data_path: str,
    job_id: str,
    registry_lock_timeout_seconds: int = 30,
) -> CycleResult:
    """
    Run one complete continuous-learning cycle.

    Parameters
    ----------
    config_path   : path to fine_tuning/config.yaml on the pod
    new_data_path : path to the JSONL snapshot (from version_store)
    job_id        : unique identifier for this cycle (used in output paths)
    registry_lock_timeout_seconds: max wait for the file-based registry lock

    Returns
    -------
    CycleResult with status, version, paths, gate result, and error info.
    """
    from fine_tuning.config_schema import load_and_validate_config
    from fine_tuning.dataset.dataset_builder import DatasetBuilder, InsufficientDataError
    from fine_tuning.registry.version_registry import VersionRegistry
    from fine_tuning.continuous_learning.version_store import RegistryLock
    from fine_tuning.train import run_training
    from fine_tuning.training.merger import AdapterMerger
    from fine_tuning.evaluation.local_metrics import run_local_eval
    from fine_tuning.evaluation.deepeval_runner import run_deepeval
    from fine_tuning.evaluation.forgetting_eval import ForgettingEvaluator
    from fine_tuning.evaluation.eval_gate import run_eval_gate
    from fine_tuning.training_orchestrator import promote_adapter

    started_at = _utc_now()
    cycle_id   = str(uuid.uuid4())[:12]

    _set_job(job_id, {
        "job_id":     job_id,
        "cycle_id":   cycle_id,
        "status":     "running",
        "phase":      "starting",
        "started_at": started_at,
        "finished_at": None,
        "error":      None,
        "version":    None,
        "gate_passed": None,
    })

    def _update(phase: str, **kwargs: Any) -> None:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["phase"] = phase
                _jobs[job_id].update(kwargs)

    try:
        # ── 1. Load and validate config ───────────────────────────────────────
        _update("loading_config")
        config = load_and_validate_config(config_path)
        paths_cfg  = config["paths"]
        runs_dir   = Path(paths_cfg["runs_dir"])
        reg_path   = paths_cfg["registry_path"]
        runs_dir.mkdir(parents=True, exist_ok=True)

        _check_eval_files(config)

        # ── 2. Acquire registry lock (prevent concurrent cycles) ───────────────
        feedback_dir = config["continuous_learning"]["feedback_datasets_dir"]
        lock_root    = Path(feedback_dir)

        with RegistryLock(lock_root, timeout_seconds=registry_lock_timeout_seconds):

            # ── 3. Build dataset ──────────────────────────────────────────────
            _update("building_dataset")
            builder = DatasetBuilder(config)
            try:
                build_result = builder.build(
                    new_data_path=new_data_path,
                    cycle_id=cycle_id,
                    min_records=1,
                )
            except InsufficientDataError as e:
                raise RuntimeError(str(e))

            print(
                f"[job_runner] Dataset: {build_result.total_records} rows "
                f"({build_result.new_records} new + {build_result.replay_records} replay, "
                f"{build_result.rejected_records} rejected)"
            )

            # ── 4. Resolve base model ─────────────────────────────────────────
            _update("resolving_base_model")
            base_model = _resolve_base_model(config, reg_path)

            # ── 5. Create pending registry entry ─────────────────────────────
            registry = VersionRegistry(reg_path)
            parent_version = registry.get_current_version()
            replay_fraction = float(config.get("training", {}).get("replay_fraction", 0.30))
            run_output_dir  = runs_dir / f"{cycle_id}-adapter"

            new_version = registry.create_pending_entry(
                cycle_id=cycle_id,
                job_id=job_id,
                parent_version=parent_version,
                replay_fraction=replay_fraction,
                checkpoint_dir=str(run_output_dir),
            )
            _update("pending_registered", version=new_version)

            # ── 6. Train (QLoRA SFT) ──────────────────────────────────────────
            _update("training")
            print(f"[job_runner] Starting QLoRA training — version={new_version} …")
            adapter_path = run_training(
                config=config,
                dataset_path=build_result.train_jsonl_path,
                output_dir=str(run_output_dir),
                job_id=job_id,
                base_model=base_model,
            )

            # ── 7. Evaluation ─────────────────────────────────────────────────
            _update("evaluating")
            eval_examples = _load_eval_examples_from_config(config)
            print(f"[job_runner] Running local eval on {len(eval_examples)} examples …")

            local_result     = run_local_eval(adapter_path, config, eval_examples)
            deepeval_result  = run_deepeval(adapter_path, config, eval_examples)

            parent_scores = None
            if parent_version > 0:
                versions = registry.list_versions()
                for v in versions:
                    if v["version"] == parent_version:
                        parent_scores = v.get("eval_scores") or {}
                        break

            forgetting = ForgettingEvaluator(config).evaluate(
                adapter_path=adapter_path,
                parent_eval_examples=eval_examples,
                parent_version_scores=parent_scores,
            )

            gate = run_eval_gate(
                local_result, deepeval_result, parent_scores, config, forgetting
            )
            _update("gate_checked", gate_passed=gate.passed, eval_scores=gate.scores)

            print(
                f"[job_runner] Gate: passed={gate.passed}  "
                f"scores={gate.scores}  failures={gate.failures}"
            )

            if not gate.passed:
                registry.mark_failed(new_version, "; ".join(gate.failures))
                finished_at = _utc_now()
                _set_job(job_id, {
                    **_jobs.get(job_id, {}),
                    "status":      "gate_failed",
                    "phase":       "done",
                    "finished_at": finished_at,
                    "gate_passed": False,
                    "error":       "; ".join(gate.failures),
                })
                return CycleResult(
                    status="gate_failed",
                    cycle_id=cycle_id,
                    version=new_version,
                    adapter_path=adapter_path,
                    merged_model_path=None,
                    gate_passed=False,
                    eval_scores=gate.scores,
                    error="; ".join(gate.failures),
                    started_at=started_at,
                    finished_at=finished_at,
                )

            # ── 8. Merge adapter → full weights ───────────────────────────────
            _update("merging")
            merged_dir = str(runs_dir / f"{new_version}-{cycle_id}-merged")
            merger     = AdapterMerger()
            merge_result = merger.merge(
                adapter_path=adapter_path,
                base_model_path=base_model,
                output_path=merged_dir,
                config=config,
                cycle_id=cycle_id,
                version=new_version,
            )

            # ── 9. Promote (registry + SeaweedFS + model card + alert) ────────
            _update("promoting")
            training_meta = {
                "backend":       "qlora_hf",
                "fingerprint":   build_result.fingerprint,
                "job_id":        job_id,
                "base_model":    base_model,
                "replay_fraction": replay_fraction,
            }
            promote_adapter(
                adapter_id=job_id,
                registry_path=reg_path,
                version=new_version,
                merged_model_path=merge_result.output_path,
                adapter_path=adapter_path,
                eval_scores=gate.scores,
                training_meta=training_meta,
                base_model=base_model,
            )

        # ── Done ──────────────────────────────────────────────────────────────
        finished_at = _utc_now()
        _set_job(job_id, {
            **(_jobs.get(job_id) or {}),
            "status":             "completed",
            "phase":              "done",
            "finished_at":        finished_at,
            "gate_passed":        True,
            "version":            new_version,
            "adapter_path":       adapter_path,
            "merged_model_path":  merge_result.output_path,
            "eval_scores":        gate.scores,
        })
        print(f"[job_runner] Cycle complete — SLM v1.{new_version} promoted.")

        return CycleResult(
            status="completed",
            cycle_id=cycle_id,
            version=new_version,
            adapter_path=adapter_path,
            merged_model_path=merge_result.output_path,
            gate_passed=True,
            eval_scores=gate.scores,
            error=None,
            started_at=started_at,
            finished_at=finished_at,
        )

    except Exception as exc:
        finished_at = _utc_now()
        err_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
        print(f"[job_runner] Cycle FAILED: {err_msg}")
        _set_job(job_id, {
            **(_jobs.get(job_id) or {}),
            "status":      "failed",
            "phase":       "done",
            "finished_at": finished_at,
            "error":       str(exc),
        })
        return CycleResult(
            status="failed",
            cycle_id=cycle_id,
            version=None,
            adapter_path=None,
            merged_model_path=None,
            gate_passed=False,
            eval_scores={},
            error=str(exc),
            started_at=started_at,
            finished_at=finished_at,
        )


# ── Background launcher ───────────────────────────────────────────────────────

def launch_cycle_background(
    config_path: str,
    new_data_path: str,
    job_id: str,
) -> None:
    """Spawn run_cycle() in a daemon thread so server.py can return immediately."""
    t = threading.Thread(
        target=run_cycle,
        args=(config_path, new_data_path, job_id),
        daemon=True,
        name=f"finetune-{job_id[:8]}",
    )
    t.start()
    print(f"[job_runner] Fine-tuning launched in background thread (job_id={job_id})")
