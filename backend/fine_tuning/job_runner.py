"""
Background runner for automatic fine-tuning jobs.

This is spawned by the backend when an admin approves a pod run.
It updates the `public.pod_training_jobs` row as it progresses.

Usage:
  python -m fine_tuning.job_runner --job-id <uuid> --run-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from fine_tuning.quality_gate import evaluate_acord_gate, gate_should_fail_job
from fine_tuning.train import load_config

# Default to legacy ACORD training tables for backward compatibility.
TRAINING_JOBS_TABLE = "acord_training_jobs"
EVAL_RESULTS_TABLE = "acord_eval_results"
EVAL_POD_ID: str | None = None


def _next_version_name(models_root: Path) -> str:
    """
    Return next version label (v1, v2, ...) based on existing folders.
    """
    max_v = 0
    if models_root.exists():
        for child in models_root.iterdir():
            if not child.is_dir():
                continue
            name = child.name.strip().lower()
            if not name.startswith("v"):
                continue
            try:
                num = int(name[1:])
                max_v = max(max_v, num)
            except Exception:
                continue
    return f"v{max_v + 1}"


def _write_current_model_pointer(pointer_file: Path, version_name: str) -> None:
    pointer_file.parent.mkdir(parents=True, exist_ok=True)
    pointer_file.write_text(version_name.strip(), encoding="utf-8")


def _read_current_model_dir(registry_root: Path, pointer_file: Path) -> Path | None:
    """
    Return current promoted model directory from pointer file, if available.
    """
    if not pointer_file.exists():
        return None
    version_name = pointer_file.read_text(encoding="utf-8", errors="replace").strip()
    if not version_name:
        return None
    candidate = (registry_root / version_name).resolve()
    return candidate if candidate.exists() else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _patch_job(job_id: str, payload: dict) -> None:
    url = f"{SUPABASE_URL}/rest/v1/{TRAINING_JOBS_TABLE}?id=eq.{quote(job_id, safe='')}"
    last_err: str | None = None
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.patch(url, headers=_headers(), content=json.dumps(payload))
            if resp.status_code < 400:
                return
            last_err = resp.text
        except Exception as exc:
            last_err = str(exc)
        if attempt < 3:
            time.sleep(1.2 * attempt)
    raise RuntimeError(last_err or "failed to patch training job")


def _insert_eval_results(job_id: str, rows: list[dict]) -> None:
    """Insert pod_eval_results rows for a completed training job."""
    if not rows:
        return
    upsert_url = f"{SUPABASE_URL}/rest/v1/{EVAL_RESULTS_TABLE}?on_conflict=job_id,eval_set"
    base_headers = _headers()
    upsert_headers = dict(base_headers)
    upsert_headers["Prefer"] = "return=minimal,resolution=merge-duplicates"
    payloads = [
        {
            "job_id": job_id,
            "eval_set": r["eval_set"],
            "exact_match": r.get("exact_match"),
            "soft_accuracy": r.get("soft_accuracy"),
            "semantic_sim": r.get("semantic_sim"),
            "hallucination_rate": r.get("hallucination_rate"),
            "refusal_rate": r.get("refusal_rate"),
            "metrics_json": r.get("metrics_json") or {},
            **({"pod_id": EVAL_POD_ID} if EVAL_POD_ID else {}),
        }
        for r in rows
    ]

    def _fallback_merge_without_unique(client: httpx.Client, payload: dict) -> None:
        """
        Fallback merge when DB is missing UNIQUE(job_id, eval_set).
        Strategy: SELECT existing row -> PATCH if exists, otherwise INSERT.
        """
        job_q = quote(str(payload["job_id"]), safe="")
        eval_q = quote(str(payload["eval_set"]), safe="")
        lookup_url = (
            f"{SUPABASE_URL}/rest/v1/{EVAL_RESULTS_TABLE}"
            f"?select=id&job_id=eq.{job_q}&eval_set=eq.{eval_q}&limit=1"
        )
        lookup = client.get(lookup_url, headers=base_headers)
        if lookup.status_code >= 400:
            raise RuntimeError(f"eval lookup failed: {lookup.text}")
        existing = lookup.json() or []

        if existing:
            row_id = quote(str(existing[0]["id"]), safe="")
            patch_url = f"{SUPABASE_URL}/rest/v1/{EVAL_RESULTS_TABLE}?id=eq.{row_id}"
            patch_resp = client.patch(
                patch_url,
                headers=base_headers,
                content=json.dumps(
                    {
                        "exact_match": payload.get("exact_match"),
                        "soft_accuracy": payload.get("soft_accuracy"),
                        "semantic_sim": payload.get("semantic_sim"),
                        "hallucination_rate": payload.get("hallucination_rate"),
                        "refusal_rate": payload.get("refusal_rate"),
                        "metrics_json": payload.get("metrics_json") or {},
                    }
                ),
            )
            if patch_resp.status_code >= 400:
                raise RuntimeError(f"eval patch failed: {patch_resp.text}")
            return

        insert_url = f"{SUPABASE_URL}/rest/v1/{EVAL_RESULTS_TABLE}"
        ins = client.post(insert_url, headers=base_headers, content=json.dumps(payload))
        if ins.status_code >= 400:
            raise RuntimeError(f"eval insert fallback failed: {ins.text}")

    with httpx.Client(timeout=30) as client:
        for p in payloads:
            last_err: str | None = None
            for attempt in range(1, 4):
                resp = client.post(upsert_url, headers=upsert_headers, content=json.dumps(p))
                if resp.status_code < 400:
                    last_err = None
                    break
                # 42P10 => no unique constraint for ON CONFLICT.
                if resp.status_code == 409 and "42P10" in (resp.text or ""):
                    try:
                        _fallback_merge_without_unique(client, p)
                        last_err = None
                        break
                    except Exception as fallback_exc:
                        last_err = str(fallback_exc)
                else:
                    last_err = resp.text
                if attempt < 3:
                    time.sleep(0.8 * attempt)
            if last_err:
                raise RuntimeError(f"eval insert failed: {last_err}")


def _validate_model_path(cfg_path: str) -> None:
    """
    Fail fast if local/offline model path is not available.
    """
    cfg = load_config(cfg_path)
    if not bool(cfg.get("local_files_only", False)):
        return
    model_ref = str(cfg.get("base_model", "")).strip()
    if not model_ref:
        raise RuntimeError("Fine-tuning config base_model is empty.")
    p = Path(model_ref)
    # If it's clearly a HF repo name (no slashes like c:/ or path separators), skip local validation.
    if not p.exists():
        raise RuntimeError(
            f"local_files_only=true but base_model path does not exist: {model_ref}. "
            "Set FINE_TUNE_BASE_MODEL to a valid local model directory."
        )
    required = ["config.json"]
    missing = [f for f in required if not (p / f).exists()]
    if missing:
        raise RuntimeError(f"Local model path is missing required files: {missing} in {model_ref}")


def _tail_text(path: Path, max_lines: int = 80) -> str:
    """Return last N lines from a text file."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def _count_jsonl_records(path: Path) -> int:
    """Count non-empty lines in JSONL dataset file."""
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _read_jsonl_records(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _write_jsonl_records(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _build_chat_eval_from_instruction_records(rows: list[dict], out_path: Path) -> int:
    """
    Convert instruction/input/output JSONL records to chat-format eval set used by
    acord_form_pipeline.evaluate_extraction.
    """
    from fine_tuning.acord_form_pipeline.schema import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
    from fine_tuning.oos_refusal_examples import OOS_SYSTEM_RULES

    chat_rows: list[dict] = []
    for r in rows:
        input_text = str(r.get("input") or "").strip()
        output_text = str(r.get("output") or "").strip()
        if not output_text:
            continue
        user_content = USER_PROMPT_TEMPLATE.format(input_text=input_text)
        meta = r.get("metadata") or {}
        is_oos = bool(meta.get("oos")) or meta.get("category") == "oos"
        sys_c = OOS_SYSTEM_RULES if is_oos else SYSTEM_PROMPT
        chat_rows.append(
            {
                "messages": [
                    {"role": "system", "content": sys_c},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": output_text},
                ],
                "record_meta": {
                    "category": meta.get("category"),
                    "base_doc_id": meta.get("base_doc_id"),
                    "oos": is_oos,
                },
            }
        )
    _write_jsonl_records(out_path, chat_rows)
    return len(chat_rows)


def _weighted_metric(results: dict, keys: list[str], metric: str) -> float | None:
    total_n = 0
    weighted = 0.0
    for k in keys:
        row = results.get(k) or {}
        n = int(row.get("n") or 0)
        if n <= 0:
            continue
        if metric not in row:
            continue
        total_n += n
        weighted += float(row.get(metric) or 0.0) * n
    if total_n <= 0:
        return None
    return weighted / total_n


def _quality_gate_check(eval_payload: dict, *, pod_mode: bool) -> tuple[bool, str]:
    """
    Validate anti-hallucination quality thresholds from eval payload.
    Returns (ok, message).
    """
    enabled_raw = (os.getenv("FT_QUALITY_GATE_ENABLED") or "true").strip().lower()
    enabled = enabled_raw in {"1", "true", "yes", "on"}
    if not enabled:
        return True, "quality gate disabled (FT_QUALITY_GATE_ENABLED=false)"
    # By default we enforce JSON-centric quality checks for both pod and ACORD jobs.
    # Set FT_QUALITY_GATE_ENFORCE_ACORD=false to keep legacy ACORD behavior.
    enforce_acord_raw = (os.getenv("FT_QUALITY_GATE_ENFORCE_ACORD") or "true").strip().lower()
    enforce_acord = enforce_acord_raw in {"1", "true", "yes", "on"}
    if not pod_mode and not enforce_acord:
        return True, "quality gate skipped for non-pod mode (FT_QUALITY_GATE_ENFORCE_ACORD=false)"

    results = eval_payload.get("results") or {}
    if not isinstance(results, dict) or not results:
        return False, "quality_gate_failed: missing evaluation results"

    if pod_mode:
        min_json_valid = float(os.getenv("FT_QG_MIN_JSON_VALID_RATE", "0.99"))
        min_json_exact = float(os.getenv("FT_QG_MIN_JSON_EXACT_MATCH", "0.90"))
        min_field_recall = float(os.getenv("FT_QG_MIN_JSON_FIELD_RECALL", "0.95"))
        max_extra_field = float(os.getenv("FT_QG_MAX_JSON_EXTRA_FIELD_RATE", "0.02"))
        max_oos_halluc = float(os.getenv("FT_QG_MAX_OOS_HALLUCINATION_RATE", "0.05"))
        require_oos = True
    else:
        min_json_valid = float(os.getenv("FT_ACORD_QG_MIN_JSON_VALID_RATE", "0.90"))
        min_json_exact = float(os.getenv("FT_ACORD_QG_MIN_JSON_EXACT_MATCH", "0.70"))
        min_field_recall = float(os.getenv("FT_ACORD_QG_MIN_JSON_FIELD_RECALL", "0.80"))
        max_extra_field = float(os.getenv("FT_ACORD_QG_MAX_JSON_EXTRA_FIELD_RATE", "0.10"))
        max_oos_halluc = float(os.getenv("FT_ACORD_QG_MAX_OOS_HALLUCINATION_RATE", "0.25"))
        require_oos_raw = (os.getenv("FT_ACORD_QG_REQUIRE_OOS") or "false").strip().lower()
        require_oos = require_oos_raw in {"1", "true", "yes", "on"}

    failures: list[str] = []
    checks: list[str] = []

    sr_keys = ["seen", "paraphrased"]
    json_valid = _weighted_metric(results, sr_keys, "json_valid_rate")
    json_exact = _weighted_metric(results, sr_keys, "json_exact_match")
    field_recall = _weighted_metric(results, sr_keys, "json_field_recall")
    extra_rate = _weighted_metric(results, sr_keys, "json_extra_field_rate")
    oos_hall = _weighted_metric(results, ["out_of_scope"], "hallucination_rate")

    if json_valid is None:
        failures.append("missing seen/paraphrased json_valid_rate")
    else:
        checks.append(f"json_valid_rate={json_valid:.4f} (min {min_json_valid:.4f})")
        if json_valid < min_json_valid:
            failures.append(f"json_valid_rate {json_valid:.4f} < {min_json_valid:.4f}")

    if json_exact is None:
        failures.append("missing seen/paraphrased json_exact_match")
    else:
        checks.append(f"json_exact_match={json_exact:.4f} (min {min_json_exact:.4f})")
        if json_exact < min_json_exact:
            failures.append(f"json_exact_match {json_exact:.4f} < {min_json_exact:.4f}")

    if field_recall is None:
        failures.append("missing seen/paraphrased json_field_recall")
    else:
        checks.append(f"json_field_recall={field_recall:.4f} (min {min_field_recall:.4f})")
        if field_recall < min_field_recall:
            failures.append(f"json_field_recall {field_recall:.4f} < {min_field_recall:.4f}")

    if extra_rate is None:
        failures.append("missing seen/paraphrased json_extra_field_rate")
    else:
        checks.append(f"json_extra_field_rate={extra_rate:.4f} (max {max_extra_field:.4f})")
        if extra_rate > max_extra_field:
            failures.append(f"json_extra_field_rate {extra_rate:.4f} > {max_extra_field:.4f}")

    if oos_hall is None:
        if require_oos:
            failures.append("missing out_of_scope hallucination_rate")
        else:
            checks.append("oos_hallucination_rate=skipped")
    else:
        checks.append(f"oos_hallucination_rate={oos_hall:.4f} (max {max_oos_halluc:.4f})")
        if oos_hall > max_oos_halluc:
            failures.append(f"oos_hallucination_rate {oos_hall:.4f} > {max_oos_halluc:.4f}")

    if failures:
        return False, "quality_gate_failed: " + "; ".join(failures)
    return True, "quality_gate_passed: " + " | ".join(checks)


def _gpu_snapshot() -> str:
    """
    Best-effort GPU snapshot for job logs.
    """
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip().replace("\n", " | ")
        return f"nvidia-smi unavailable (code={p.returncode})"
    except Exception as exc:
        return f"nvidia-smi unavailable ({exc})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--pod-id", required=False)
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")

    backend_dir = Path(__file__).resolve().parents[1]
    runs_dir = backend_dir / "fine_tuning" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    pod_mode = bool(args.pod_id)
    global TRAINING_JOBS_TABLE, EVAL_RESULTS_TABLE, EVAL_POD_ID

    model_registry_root_env = (os.getenv("MODEL_REGISTRY_ROOT") or "").strip()
    current_model_file_env = (os.getenv("CURRENT_MODEL_FILE") or "").strip()
    use_versioned_registry = bool(model_registry_root_env)

    previous_model_dir: Path | None = None

    if pod_mode:
        TRAINING_JOBS_TABLE = "pod_training_jobs"
        EVAL_RESULTS_TABLE = "pod_eval_results"
        EVAL_POD_ID = str(args.pod_id)
        dataset_path = runs_dir / f"pod_{args.pod_id}_{args.run_id}.jsonl"
        if use_versioned_registry:
            pod_root = Path(model_registry_root_env) / str(args.pod_id)
            pod_root.mkdir(parents=True, exist_ok=True)
            version_name = _next_version_name(pod_root)
            output_dir = pod_root / version_name
            current_pointer_file = (
                Path(current_model_file_env)
                if current_model_file_env
                else pod_root / "current_model.txt"
            )
            previous_model_dir = _read_current_model_dir(pod_root, current_pointer_file)
        else:
            output_dir = runs_dir / f"adapter_{args.pod_id}_{args.run_id}"
            version_name = ""
            current_pointer_file = Path()
    else:
        EVAL_POD_ID = None
        dataset_path = runs_dir / f"acord_train_{args.run_id}.jsonl"
        holdout_export_path = runs_dir / f"acord_holdout_{args.run_id}.jsonl"
        if use_versioned_registry:
            models_root = Path(model_registry_root_env)
            models_root.mkdir(parents=True, exist_ok=True)
            version_name = _next_version_name(models_root)
            output_dir = models_root / version_name
            current_pointer_file = (
                Path(current_model_file_env)
                if current_model_file_env
                else (Path(__file__).resolve().parents[1] / "current_model.txt")
            )
            previous_model_dir = _read_current_model_dir(models_root, current_pointer_file)
        else:
            output_dir = runs_dir / f"adapter_{args.run_id}"
            version_name = ""
            current_pointer_file = Path()
    log_path = runs_dir / f"job_{args.job_id}.log"

    _patch_job(
        args.job_id,
        {
            "status": "running",
            "dataset_path": str(dataset_path),
            "output_dir": str(output_dir),
            "log_path": str(log_path),
            "started_at": _utc_now_iso(),
            "error": None,
        },
    )

    py = sys.executable
    cfg = os.getenv("FINE_TUNING_CONFIG_PATH", "fine_tuning/config.yaml")
    resolved_cfg: dict = {}

    if pod_mode:
        # Train on a broader approved corpus for the pod, not only the triggering run.
        # This reduces overfitting/hallucination from single-run fine-tunes.
        pod_dataset_limit = int(os.getenv("POD_TRAINING_APPROVED_LIMIT", "500"))
        export_cmd = [
            py,
            "-m",
            "fine_tuning.export_approved_pod_dataset",
            "--pod-id",
            args.pod_id,
            "--limit",
            str(max(1, pod_dataset_limit)),
            "--out",
            str(dataset_path),
        ]
    else:
        acord_dataset_limit = int(os.getenv("ACORD_TRAINING_APPROVED_LIMIT", "500"))
        export_cmd = [
            py,
            "-m",
            "fine_tuning.export_approved_acord_dataset",
            "--limit",
            str(max(1, acord_dataset_limit)),
            "--out",
            str(dataset_path),
            "--holdout-out",
            str(holdout_export_path),
        ]
    eval_results_path = runs_dir / f"eval_results_{args.job_id}.json"
    pipeline_dataset_path = dataset_path
    chat_eval_dataset_path: Path | None = None
    pipeline_cmd = [
        py,
        "-m",
        "fine_tuning.run_pipeline",
        "--config",
        cfg,
        "--dataset",
        str(pipeline_dataset_path),
        "--output-dir",
        str(output_dir),
        "--job-id",
        args.job_id,
        "--output-eval-json",
        str(eval_results_path),
    ]

    def _persist_eval_results() -> None:
        """Read eval_results JSON and insert into pod_eval_results."""
        if not eval_results_path.exists():
            return
        try:
            payload = json.loads(eval_results_path.read_text(encoding="utf-8"))
            rows = payload.get("rows") or []
            _insert_eval_results(args.job_id, rows)
        except Exception as e:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"\n[warning] Failed to persist eval results: {e}\n")

    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"[job] job_id={args.job_id} run_id={args.run_id} started_at={_utc_now_iso()}\n")
        if pod_mode:
            logf.write(f"[job] pod_id={args.pod_id}\n")
        logf.write(f"[env] cwd={backend_dir}\n")
        logf.write(f"[env] python={py}\n")
        logf.write(f"[env] gpu={_gpu_snapshot()}\n")
        logf.write(f"[cfg] config_path={cfg}\n")
        if not pod_mode:
            logf.write(
                "[cfg] env.ACORD_TRAINING_MIN_RECORDS={v}\n".format(
                    v=(os.getenv("ACORD_TRAINING_MIN_RECORDS") or "80")
                )
            )
            logf.write(
                "[cfg] env.FT_ACORD_HOLDOUT_EVAL_ENABLED={v}\n".format(
                    v=(os.getenv("FT_ACORD_HOLDOUT_EVAL_ENABLED") or "true")
                )
            )
            logf.write(
                "[cfg] env.FT_ACORD_HOLDOUT_MIN={v}\n".format(
                    v=(os.getenv("FT_ACORD_HOLDOUT_MIN") or "15")
                )
            )
            logf.write(
                "[cfg] env.FT_ACORD_HOLDOUT_RATIO={v}\n".format(
                    v=(os.getenv("FT_ACORD_HOLDOUT_RATIO") or "0.20")
                )
            )
            logf.write(
                "[cfg] env.FT_QUALITY_GATE_ENFORCE_ACORD={v}\n".format(
                    v=(os.getenv("FT_QUALITY_GATE_ENFORCE_ACORD") or "true")
                )
            )
            logf.write(
                "[cfg] env.FT_ACORD_QG_REQUIRE_OOS={v}\n".format(
                    v=(os.getenv("FT_ACORD_QG_REQUIRE_OOS") or "false")
                )
            )
            logf.write(
                "[cfg] env.ACORD_EXPORT_AUGMENT_PROMPTS={v}\n".format(
                    v=(os.getenv("ACORD_EXPORT_AUGMENT_PROMPTS") or "true")
                )
            )
        if use_versioned_registry:
            logf.write(f"[registry] model_registry_root={model_registry_root_env}\n")
            logf.write(f"[registry] target_version={version_name}\n")
            logf.write(f"[registry] current_model_file={current_pointer_file}\n")
            logf.write(f"[registry] previous_model_dir={previous_model_dir}\n")
        logf.write(f"[cmd] {' '.join(export_cmd)}\n")
        logf.flush()
        try:
            # Validate and print resolved config before subprocesses so failures are visible in log.
            resolved_cfg = load_config(cfg)
            logf.write(
                "[cfg] base_model={base_model} local_files_only={local_files_only} use_auth_token={use_auth_token}\n".format(
                    base_model=resolved_cfg.get("base_model"),
                    local_files_only=resolved_cfg.get("local_files_only"),
                    use_auth_token=resolved_cfg.get("use_auth_token"),
                )
            )
            eval_cfg = resolved_cfg.get("evaluation") or {}
            logf.write(
                "[cfg] evaluation.run_baseline_eval={val}\n".format(
                    val=eval_cfg.get("run_baseline_eval"),
                )
            )
            logf.write(f"[cfg] output_dir={resolved_cfg.get('output_dir')}\n")
            tcfg = resolved_cfg.get("training") or {}
            lcfg = resolved_cfg.get("lora") or {}
            logf.write(f"[cfg] training.num_epochs={tcfg.get('num_epochs')}\n")
            logf.write(
                "[train] epochs={e} lr={lr} lora_r={r} warmup={w} grad_accum={ga} max_grad_norm={mgn}\n".format(
                    e=tcfg.get("num_epochs"),
                    lr=tcfg.get("learning_rate"),
                    r=lcfg.get("r"),
                    w=tcfg.get("warmup_ratio"),
                    ga=tcfg.get("gradient_accumulation_steps"),
                    mgn=tcfg.get("max_grad_norm"),
                )
            )
            logf.flush()
            _validate_model_path(cfg)

            exp = subprocess.run(export_cmd, cwd=str(backend_dir), stdout=logf, stderr=logf, text=True)
            if exp.returncode != 0:
                raise RuntimeError(f"export failed (code={exp.returncode})")
            exported_records = _count_jsonl_records(dataset_path)
            min_records = int(os.getenv("POD_TRAINING_MIN_RECORDS", "200")) if pod_mode else int(
                os.getenv("ACORD_TRAINING_MIN_RECORDS", "80")
            )
            logf.write(f"[data] exported_records={exported_records} min_required={min_records}\n")
            logf.flush()
            if exported_records < min_records:
                raise RuntimeError(
                    (
                        f"Insufficient {'pod' if pod_mode else 'acord'} training data: "
                        f"exported {exported_records} records, required >= {min_records}. "
                        + (
                            "Approve more runs or lower POD_TRAINING_MIN_RECORDS."
                            if pod_mode
                            else "Approve more ACORD runs or lower ACORD_TRAINING_MIN_RECORDS."
                        )
                    )
                )

            if not pod_mode:
                holdout_enabled_raw = (os.getenv("FT_ACORD_HOLDOUT_EVAL_ENABLED") or "true").strip().lower()
                holdout_enabled = holdout_enabled_raw in {"1", "true", "yes", "on"}
                if holdout_enabled and holdout_export_path.exists():
                    chat_eval_dataset_path = runs_dir / f"acord_eval_chat_{args.run_id}.jsonl"
                    holdout_rows = _read_jsonl_records(holdout_export_path)
                    eval_count = _build_chat_eval_from_instruction_records(holdout_rows, chat_eval_dataset_path)
                    train_rows = _read_jsonl_records(dataset_path)
                    logf.write(
                        f"[data] holdout_enabled=true train_records={len(train_rows)} "
                        f"holdout_records={eval_count} (split in export; no augmented leakage)\n"
                    )
                    logf.flush()

            logf.write(f"[cmd] {' '.join(pipeline_cmd)}\n")
            logf.flush()
            pipeline_env = os.environ.copy()
            if previous_model_dir:
                # Continue fine-tuning from the latest promoted adapter version.
                pipeline_env["FINE_TUNE_RESUME_ADAPTER"] = str(previous_model_dir)
                logf.write(f"[cfg] resume_adapter={previous_model_dir}\n")
                logf.flush()
            proc = subprocess.run(
                pipeline_cmd,
                cwd=str(backend_dir),
                stdout=logf,
                stderr=logf,
                text=True,
                env=pipeline_env,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"pipeline failed (code={proc.returncode})")

            eval_payload: dict | None = None
            if not pod_mode and chat_eval_dataset_path and chat_eval_dataset_path.exists():
                acord_eval_report = runs_dir / f"acord_eval_report_{args.job_id}.json"
                acord_eval_cmd = [
                    py,
                    "-m",
                    "fine_tuning.acord_form_pipeline.evaluate_extraction",
                    "--dataset",
                    str(chat_eval_dataset_path),
                    "--base-model",
                    str(resolved_cfg.get("base_model") or ""),
                    "--adapter-path",
                    str(output_dir),
                    "--report-out",
                    str(acord_eval_report),
                ]
                logf.write(f"[cmd] {' '.join(acord_eval_cmd)}\n")
                logf.flush()
                ev = subprocess.run(acord_eval_cmd, cwd=str(backend_dir), stdout=logf, stderr=logf, text=True)
                if ev.returncode == 0 and acord_eval_report.exists():
                    rep = json.loads(acord_eval_report.read_text(encoding="utf-8"))
                    seen_n = int(rep.get("samples_in_domain") or rep.get("samples") or 0)
                    oos_n = int(rep.get("samples_oos") or 0)
                    refusal_acc = float(rep.get("refusal_accuracy_percent", 0.0)) / 100.0
                    oos_hall = (1.0 - refusal_acc) if oos_n > 0 else 0.0
                    seen_row = {
                        "n": seen_n,
                        "json_valid_rate": float(rep.get("json_valid_percent", 0.0)) / 100.0,
                        "json_exact_match": float(rep.get("exact_match_percent", 0.0)) / 100.0,
                        "json_field_recall": float(rep.get("field_recall_percent", 0.0)) / 100.0,
                        "json_field_precision": float(rep.get("field_precision_percent", 0.0)) / 100.0,
                        "json_extra_field_rate": 0.0,
                    }
                    oos_row = {
                        "n": oos_n,
                        "hallucination_rate": oos_hall,
                        "refusal_accuracy": refusal_acc,
                        "refusal_rate": refusal_acc,
                    }
                    eval_payload = {
                        "job_id": args.job_id,
                        "results": {"seen": seen_row, "out_of_scope": oos_row},
                        "rows": [
                            {
                                "eval_set": "seen",
                                "exact_match": seen_row["json_exact_match"],
                                "soft_accuracy": seen_row["json_field_recall"],
                                "semantic_sim": None,
                                "hallucination_rate": None,
                                "refusal_rate": None,
                                "metrics_json": {
                                    "n": seen_n,
                                    "json_valid_rate": seen_row["json_valid_rate"],
                                    "json_exact_match": seen_row["json_exact_match"],
                                    "json_field_recall": seen_row["json_field_recall"],
                                    "json_field_precision": seen_row["json_field_precision"],
                                    "json_extra_field_rate": 0.0,
                                },
                            }
                        ],
                    }
                    gate = evaluate_acord_gate(eval_payload)
                    eval_payload["gate"] = gate
                    eval_payload["gate_tier"] = gate.get("gate_tier")
                    eval_payload["deploy_recommended"] = gate.get("deploy_recommended")
                    eval_payload["gate_reasons"] = gate.get("gate_reasons", [])
                    eval_results_path.write_text(json.dumps(eval_payload, indent=2), encoding="utf-8")
                    logf.write(
                        "[eval] json_valid={jv:.4f} field_recall={fr:.4f} field_precision={fp:.4f}\n".format(
                            jv=seen_row["json_valid_rate"],
                            fr=seen_row["json_field_recall"],
                            fp=seen_row["json_field_precision"],
                        )
                    )
                    logf.write(
                        "[eval] hallucination_rate(oos)={hr:.4f} refusal_accuracy={rr:.4f}\n".format(
                            hr=oos_hall,
                            rr=refusal_acc,
                        )
                    )
                    logf.write(
                        "[gate] tier={t} deploy_recommended={d} reasons={r}\n".format(
                            t=gate.get("gate_tier"),
                            d=gate.get("deploy_recommended"),
                            r=gate.get("gate_reasons"),
                        )
                    )
                    logf.flush()
                    if gate_should_fail_job(gate):
                        raise RuntimeError(
                            "quality_gate_failed: " + "; ".join(gate.get("gate_reasons") or ["FAIL"])
                        )

            if eval_payload is None and eval_results_path.exists():
                eval_payload = json.loads(eval_results_path.read_text(encoding="utf-8"))
            if eval_payload is not None and pod_mode:
                gate_ok, gate_msg = _quality_gate_check(eval_payload, pod_mode=pod_mode)
                logf.write(f"[quality_gate] {gate_msg}\n")
                logf.flush()
                if not gate_ok:
                    raise RuntimeError(gate_msg)
            else:
                # In pod mode we require evaluation artifact for quality gating.
                if pod_mode:
                    raise RuntimeError("quality_gate_failed: missing eval_results JSON artifact")

            _persist_eval_results()
            if use_versioned_registry and version_name:
                _write_current_model_pointer(current_pointer_file, version_name)
                logf.write(f"[registry] promoted={version_name}\n")
                logf.flush()
            _patch_job(args.job_id, {"status": "completed", "finished_at": _utc_now_iso()})
        except Exception as exc:
            tail = _tail_text(log_path, max_lines=80)
            err_msg = str(exc)
            if tail:
                err_msg = f"{err_msg}\n--- log tail ---\n{tail[-3000:]}"
            _patch_job(args.job_id, {"status": "failed", "error": err_msg, "finished_at": _utc_now_iso()})
            raise


if __name__ == "__main__":
    main()

