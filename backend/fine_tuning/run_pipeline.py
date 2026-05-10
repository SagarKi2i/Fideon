"""
End-to-end pipeline: train → fine-tuned eval → (optional baseline eval after unload).

Usage:
  python -m fine_tuning.run_pipeline --config fine_tuning/config.yaml
  python -m fine_tuning.run_pipeline --config fine_tuning/config.yaml --skip-train  # eval only
  python -m fine_tuning.run_pipeline --config fine_tuning/config.yaml --train-only  # no eval
"""

import argparse
import gc
from pathlib import Path
from typing import Optional, Union

import torch

from .train import load_config, run_training
from .evaluate import load_eval_sets, run_evaluation, print_eval_report
from .inference import load_base_model_only, load_model_for_inference
from .schema import validate_dataset


def _resolve_path(cfg_path: Path, key: str, default: str) -> Path:
    p = cfg_path.parent / default
    return p.resolve()


def safe_unload_model(model, tokenizer=None, label: str = "model") -> None:
    """Unload a model and free GPU memory before loading the next one."""
    try:
        model.cpu()
    except Exception:
        pass
    del model
    if tokenizer is not None:
        del tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    if torch.cuda.is_available():
        free_gb = torch.cuda.mem_get_info()[0] / 1e9
        print(f"[vram] after unloading {label}: {free_gb:.1f} GB free")


def _serialize_eval_for_db(results: dict) -> list[dict]:
    """Convert run_evaluation output to acord_eval_results rows (one per eval_set)."""
    rows: list[dict] = []
    for eval_set, data in results.items():
        if data.get("n", 0) == 0:
            continue
        # DB check constraints use `oos` while evaluation uses `out_of_scope`.
        db_eval_set = "oos" if eval_set == "out_of_scope" else eval_set
        row: dict = {
            "eval_set": db_eval_set,
            "exact_match": None,
            "soft_accuracy": None,
            "semantic_sim": None,
            "hallucination_rate": None,
            "refusal_rate": None,
            "metrics_json": {},
        }
        if "accuracy_exact" in data:
            row["exact_match"] = data["accuracy_exact"]
            row["soft_accuracy"] = data.get("accuracy_soft")
            row["semantic_sim"] = data.get("semantic_similarity")
            row["metrics_json"] = {
                "n": data["n"],
                "similarity_bands": data.get("similarity_bands"),
            }
        else:
            row["refusal_rate"] = data.get("refusal_rate") or data.get("refusal_accuracy")
            row["hallucination_rate"] = data.get("hallucination_rate")
            row["metrics_json"] = {"n": data["n"]}
        rows.append(row)
    return rows


def run(
    config_path: Union[str, Path],
    *,
    skip_train: bool = False,
    train_only: bool = False,
    dataset_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    job_id: Optional[str] = None,
    output_eval_json: Optional[Union[str, Path]] = None,
) -> Optional[dict]:
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    config = load_config(config_path)
    base_model = config.get("base_model", "Qwen/Qwen2.5-14B-Instruct")
    local_files_only = bool(config.get("local_files_only", False))
    adapter_dir = output_dir or config.get("output_dir", "qwen25_14b_lora_adapter")
    adapter_path = Path(adapter_dir).resolve()
    base = config_path.parent

    eval_sets = load_eval_sets(config, base_path=base)
    has_eval_examples = any(bool(v) for v in eval_sets.values())
    require_json_output = bool(config.get("require_json_output", False))

    if require_json_output:
        for eval_set_name, examples in eval_sets.items():
            if not examples:
                continue
            ok, errors = validate_dataset(examples, require_json_output=True)
            if not ok:
                preview = "\n".join(errors[:10])
                raise ValueError(
                    f"Evaluation dataset '{eval_set_name}' has non-JSON outputs while require_json_output=true.\n"
                    f"{preview}\n"
                    "Run: python -m fine_tuning.prepare_staging_data --all"
                )

    run_baseline_eval = bool((config.get("evaluation", {}) or {}).get("run_baseline_eval", False))

    # --- Train ---
    if not skip_train:
        print("Starting QLoRA training...")
        run_training(
            config_path,
            dataset_path=dataset_path,
            output_dir=output_dir,
        )
        print(f"Adapter saved to: {adapter_path}")

    # --- Post-train eval (adapter) ---
    if not train_only and adapter_path.exists() and has_eval_examples:
        print("Running evaluation with fine-tuned adapter...")
        model, tokenizer = load_model_for_inference(
            base_model,
            adapter_path,
            load_in_4bit=config.get("load_in_4bit", True),
            use_auth_token=config.get("use_auth_token", False),
            local_files_only=local_files_only,
        )
        eval_cfg = config.get("evaluation", {}) or {}
        post_results = run_evaluation(
            model, tokenizer, eval_sets,
            max_new_tokens=eval_cfg.get("max_new_tokens", 256),
            temperature=eval_cfg.get("temperature", 0.0),
            use_semantic_similarity=eval_cfg.get("use_semantic_similarity", True),
            semantic_model=eval_cfg.get("semantic_similarity_model", "all-MiniLM-L6-v2"),
            use_verification=eval_cfg.get("verification_layer", False),
        )
        print_eval_report(post_results)
        safe_unload_model(model, tokenizer, "finetuned_adapter")

        # --- Baseline eval (optional, after fine-tuned model is unloaded) ---
        if run_baseline_eval and has_eval_examples and not train_only:
            if torch.cuda.is_available():
                free_gb = torch.cuda.mem_get_info()[0] / 1e9
                if free_gb < 35.0:
                    print(
                        f"[vram] WARNING: only {free_gb:.1f} GB free, "
                        "skipping baseline eval to avoid OOM"
                    )
                    run_baseline_eval = False
                    config.setdefault("evaluation", {})["run_baseline_eval"] = False
            if run_baseline_eval:
                print("Running baseline evaluation (base model, no adapter)...")
                try:
                    b_model, b_tokenizer = load_base_model_only(
                        base_model,
                        load_in_4bit=config.get("load_in_4bit", True),
                        use_auth_token=config.get("use_auth_token", False),
                        local_files_only=local_files_only,
                    )
                    baseline_results = run_evaluation(
                        b_model, b_tokenizer, eval_sets,
                        max_new_tokens=eval_cfg.get("max_new_tokens", 256),
                        temperature=eval_cfg.get("temperature", 0.0),
                        use_semantic_similarity=eval_cfg.get("use_semantic_similarity", True),
                        semantic_model=eval_cfg.get("semantic_similarity_model", "all-MiniLM-L6-v2"),
                        use_verification=eval_cfg.get("verification_layer", False),
                    )
                    print_eval_report(baseline_results)
                    safe_unload_model(b_model, b_tokenizer, "baseline_model")
                except Exception as e:
                    print(f"Baseline eval skipped: {e}")

        # Persist eval results for job association (Sprint 5)
        if output_eval_json and job_id:
            import json
            out_path = Path(output_eval_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "job_id": job_id,
                "results": post_results,
                "rows": _serialize_eval_for_db(post_results),
            }
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return post_results
    if not train_only and adapter_path.exists() and not has_eval_examples:
        print("Skipping post-train evaluation: no eval examples configured.")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tuning pipeline: train + eval")
    parser.add_argument("--config", default="fine_tuning/config.yaml", help="Path to config.yaml")
    parser.add_argument("--dataset", default=None, help="Override dataset path")
    parser.add_argument("--output-dir", default=None, help="Override adapter output dir")
    parser.add_argument("--skip-train", action="store_true", help="Only run evaluation (need existing adapter)")
    parser.add_argument("--train-only", action="store_true", help="Only train, skip evaluation")
    parser.add_argument("--job-id", default=None, help="ACORD training job ID (for eval persistence)")
    parser.add_argument("--output-eval-json", default=None, help="Write eval results to JSON file for job association")
    args = parser.parse_args()

    run(
        args.config,
        skip_train=args.skip_train,
        train_only=args.train_only,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        job_id=args.job_id,
        output_eval_json=args.output_eval_json,
    )


if __name__ == "__main__":
    main()
