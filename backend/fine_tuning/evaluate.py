"""
Evaluation for accuracy vs hallucination (workflow Steps 7–8).

Three question types:
  1. Seen: from training set (expect accurate, in-document answers).
  2. Paraphrased: same meaning as training (expect accurate).
  3. Out-of-scope: not in document (expect "not in document" / refusal).

Metrics: Exact Match, Semantic similarity (sentence-transformers), Hallucination rate, Refusal accuracy.
Bands: similarity >= 0.8 correct, 0.6–0.8 partial, < 0.6 hallucination.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .data import load_dataset_json
from .schema import TYPE_OUT_OF_SCOPE, TYPE_PARAPHRASED, TYPE_SEEN

# Semantic similarity bands for hallucination detection (Step 8)
SIM_CORRECT = 0.8   # >= 0.8: correct
SIM_PARTIAL = 0.6   # 0.6–0.8: partially correct; < 0.6: hallucination

VERIFICATION_PROMPT = (
    "Check whether the following answer is fully supported by the document. "
    "If unsupported claims exist, correct the answer. Otherwise repeat the answer as-is.\n\n"
    "Question: {instruction}\n\nAnswer to verify: {answer}\n\nCorrected or confirmed answer:"
)


# Phrases that suggest a correct "out of scope" / refusal response
OUT_OF_SCOPE_MARKERS = [
    "not in the document",
    "not present in the document",
    "not covered",
    "not found in",
    "not mentioned",
    "cannot find",
    "do not have",
    "unrelated to the document",
    "outside the scope",
    "not in this document",
]


def _is_likely_refusal(text: str) -> bool:
    """Heuristic: response looks like a refusal for out-of-scope questions."""
    lower = text.lower().strip()
    # Accept structured JSON refusal payloads for staging extraction eval.
    try:
        parsed = _try_parse_json_obj(text)
        if isinstance(parsed, dict):
            in_scope = parsed.get("in_scope")
            if in_scope is False:
                return True
            reason = str(parsed.get("refusal_reason", "")).lower()
            if "out_of_scope" in reason or "outside" in reason:
                return True
    except Exception:
        pass
    return any(m in lower for m in OUT_OF_SCOPE_MARKERS) or len(lower) < 30 and (
        "don't know" in lower or "unclear" in lower or "not" in lower
    )


def run_inference_on_examples(
    model: Any,
    tokenizer: Any,
    examples: List[Dict[str, Any]],
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.1,
) -> List[str]:
    """Generate model response for each example (instruction + input)."""
    from .inference import generate
    out = []
    for ex in examples:
        instruction = ex.get("instruction", "")
        input_text = ex.get("input") or ""
        reply = generate(
            model, tokenizer, instruction, input_text,
            max_new_tokens=max_new_tokens, temperature=temperature, do_sample=temperature > 0,
        )
        out.append(reply)
    return out


def compute_accuracy(predictions: List[str], references: List[str]) -> float:
    """Exact match is strict; for production you might use token F1 or BLEU."""
    if not references:
        return 0.0
    matches = sum(
        1 for p, r in zip(predictions, references)
        if p.strip().lower() == r.strip().lower()
    )
    return matches / len(references)


def compute_soft_accuracy(predictions: List[str], references: List[str]) -> float:
    """Score 1 if key phrases from reference appear in prediction."""
    if not references:
        return 0.0
    scores = []
    for p, r in zip(predictions, references):
        p_lower = p.lower()
        # Use first 5 words of reference as minimal "key" (or full if short)
        r_words = r.split()
        key = " ".join(r_words[:5]).lower() if len(r_words) >= 5 else r.lower()
        scores.append(1.0 if key in p_lower or key[:20] in p_lower else 0.0)
    return sum(scores) / len(scores)


def compute_semantic_similarity(
    predictions: List[str],
    references: List[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> tuple[float, List[float], Dict[str, float]]:
    """
    Compute cosine similarity between predicted and expected answers (Step 8).
    Returns: (mean_similarity, per_example_scores, bands).
    Bands: correct (>=0.8), partial (0.6–0.8), hallucination (<0.6).
    """
    if not predictions or not references or len(predictions) != len(references):
        return 0.0, [], {"correct": 0.0, "partial": 0.0, "hallucination": 0.0}
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return 0.0, [], {"correct": 0.0, "partial": 0.0, "hallucination": 0.0}

    try:
        model = SentenceTransformer(model_name)
        pred_emb = model.encode(predictions)
        ref_emb = model.encode(references)
        import numpy as np
        pred_emb = np.asarray(pred_emb)
        ref_emb = np.asarray(ref_emb)
        if pred_emb.ndim == 1:
            pred_emb = pred_emb.reshape(1, -1)
        if ref_emb.ndim == 1:
            ref_emb = ref_emb.reshape(1, -1)
        dots = np.sum(pred_emb * ref_emb, axis=1)
        norms_p = np.linalg.norm(pred_emb, axis=1)
        norms_r = np.linalg.norm(ref_emb, axis=1)
        norms_p = np.where(norms_p == 0, 1e-9, norms_p)
        norms_r = np.where(norms_r == 0, 1e-9, norms_r)
        sims = (dots / (norms_p * norms_r)).tolist()
        correct = sum(1 for s in sims if s >= SIM_CORRECT) / len(sims)
        partial = sum(1 for s in sims if SIM_PARTIAL <= s < SIM_CORRECT) / len(sims)
        halluc = sum(1 for s in sims if s < SIM_PARTIAL) / len(sims)
        return float(np.mean(sims)), sims, {"correct": correct, "partial": partial, "hallucination": halluc}
    except Exception:
        # Keep training pipeline robust when semantic model download/inference is unavailable.
        return 0.0, [], {"correct": 0.0, "partial": 0.0, "hallucination": 0.0}


def evaluate_hallucination_out_of_scope(
    predictions: List[str],
    *,
    expect_refusal: bool = True,
) -> Dict[str, float]:
    """
    For out-of-scope questions we expect refusal.
    Hallucination = answered as if in-document (no refusal).
    """
    if not predictions:
        return {"refusal_rate": 0.0, "hallucination_rate": 0.0}
    refusals = sum(1 for p in predictions if _is_likely_refusal(p))
    refusal_rate = refusals / len(predictions)
    hallucination_rate = 1.0 - refusal_rate
    return {"refusal_rate": refusal_rate, "hallucination_rate": hallucination_rate}


def _try_parse_json_obj(text: str) -> Optional[Any]:
    s = (text or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                return None
        return None


def _flatten_paths(v: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(v, dict):
        for k, child in v.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten_paths(child, p))
        return out
    if isinstance(v, list):
        for i, child in enumerate(v):
            p = f"{prefix}[{i}]" if prefix else f"[{i}]"
            out.update(_flatten_paths(child, p))
        return out
    out[prefix or "root"] = v
    return out


def compute_json_strict_metrics(predictions: List[str], references: List[str]) -> Dict[str, float]:
    """
    JSON-specific quality metrics to detect hallucination in extraction tasks.
    - valid_json_rate: prediction can be parsed as JSON
    - exact_json_match: parsed object equals reference object
    - field_precision: predicted field-path overlap precision
    - field_recall: predicted field-path overlap recall
    - extra_field_rate: hallucinated (non-reference) field ratio
    """
    if not references:
        return {
            "valid_json_rate": 0.0,
            "exact_json_match": 0.0,
            "field_precision": 0.0,
            "field_recall": 0.0,
            "extra_field_rate": 0.0,
        }

    valid = 0
    exact = 0
    p_sum = 0.0
    r_sum = 0.0
    extra_sum = 0.0
    n = min(len(predictions), len(references))
    if n == 0:
        return {
            "valid_json_rate": 0.0,
            "exact_json_match": 0.0,
            "field_precision": 0.0,
            "field_recall": 0.0,
            "extra_field_rate": 0.0,
        }

    for pred, ref in zip(predictions[:n], references[:n]):
        pred_obj = _try_parse_json_obj(pred)
        ref_obj = _try_parse_json_obj(ref)
        if pred_obj is not None:
            valid += 1
        if pred_obj is not None and ref_obj is not None and pred_obj == ref_obj:
            exact += 1

        pred_paths = set(_flatten_paths(pred_obj).keys()) if pred_obj is not None else set()
        ref_paths = set(_flatten_paths(ref_obj).keys()) if ref_obj is not None else set()

        if pred_paths:
            inter = len(pred_paths & ref_paths)
            p_sum += inter / len(pred_paths)
            extra_sum += (len(pred_paths - ref_paths) / len(pred_paths))
        else:
            p_sum += 0.0
            extra_sum += 0.0

        if ref_paths:
            inter = len(pred_paths & ref_paths)
            r_sum += inter / len(ref_paths)
        else:
            r_sum += 1.0 if not pred_paths else 0.0

    return {
        "valid_json_rate": valid / n,
        "exact_json_match": exact / n,
        "field_precision": p_sum / n,
        "field_recall": r_sum / n,
        "extra_field_rate": extra_sum / n,
    }


def load_eval_sets(
    config: Dict[str, Any],
    base_path: Optional[Path] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Load seen / paraphrased / out_of_scope from config paths."""
    eval_cfg = config.get("evaluation", {}) or {}
    base_path = base_path or Path(".")

    def load_path(key: str) -> Optional[List[Dict[str, Any]]]:
        path = eval_cfg.get(key)
        if not path:
            return None
        p = Path(path)
        if not p.is_absolute():
            p = base_path / p
        if not p.exists():
            return None
        return load_dataset_json(p)

    return {
        "seen": load_path("seen_questions_path") or [],
        "paraphrased": load_path("paraphrased_questions_path") or [],
        "out_of_scope": load_path("out_of_scope_questions_path") or [],
    }


def run_evaluation(
    model: Any,
    tokenizer: Any,
    eval_sets: Dict[str, List[Dict[str, Any]]],
    *,
    max_new_tokens: int = 256,
    temperature: float = 0.1,
    use_semantic_similarity: bool = True,
    semantic_model: str = "all-MiniLM-L6-v2",
    use_verification: bool = False,
) -> Dict[str, Any]:
    """
    Run model on each eval set and return metrics (Steps 7–8):
    - seen / paraphrased: Exact Match, Semantic similarity, similarity bands (correct/partial/hallucination).
    - out_of_scope: refusal_rate (refusal accuracy), hallucination_rate.
    """
    results = {}
    for key, examples in eval_sets.items():
        if not examples:
            results[key] = {"n": 0, "message": "No examples"}
            continue
        refs = [ex.get("output", "") for ex in examples]
        if use_verification:
            from .inference import generate_with_verification
            preds = []
            for ex in examples:
                r = generate_with_verification(
                    model, tokenizer,
                    ex.get("instruction", ""), ex.get("input") or "",
                    max_new_tokens=max_new_tokens, temperature=temperature,
                    verification_prompt=VERIFICATION_PROMPT,
                )
                preds.append(r)
        else:
            preds = run_inference_on_examples(
                model, tokenizer, examples,
                max_new_tokens=max_new_tokens, temperature=temperature,
            )
        if key == "out_of_scope":
            metrics = evaluate_hallucination_out_of_scope(preds, expect_refusal=True)
            results[key] = {
                "n": len(examples),
                "refusal_accuracy": metrics["refusal_rate"],
                "hallucination_rate": metrics["hallucination_rate"],
                **metrics,
                "predictions": preds,
            }
        else:
            exact = compute_accuracy(preds, refs)
            soft = compute_soft_accuracy(preds, refs)
            json_metrics = compute_json_strict_metrics(preds, refs)
            out = {
                "n": len(examples),
                "accuracy_exact": exact,
                "accuracy_soft": soft,
                "json_valid_rate": json_metrics["valid_json_rate"],
                "json_exact_match": json_metrics["exact_json_match"],
                "json_field_precision": json_metrics["field_precision"],
                "json_field_recall": json_metrics["field_recall"],
                "json_extra_field_rate": json_metrics["extra_field_rate"],
                "predictions": preds,
                "references": refs,
            }
            if use_semantic_similarity and refs:
                mean_sim, per_sim, bands = compute_semantic_similarity(preds, refs, semantic_model)
                out["semantic_similarity"] = mean_sim
                out["similarity_bands"] = bands
                out["per_example_similarity"] = per_sim
            results[key] = out

    return results


def print_eval_report(results: Dict[str, Any]) -> None:
    """Print evaluation report and summary metrics table (Step 10)."""
    print("\n" + "=" * 60)
    print("EVALUATION REPORT (Seen / Paraphrased / Out-of-scope)")
    print("=" * 60)
    for key, data in results.items():
        if data.get("n", 0) == 0:
            print(f"  {key}: no data")
            continue
        if "accuracy_exact" in data:
            line = f"  {key}: n={data['n']}  Exact Match={data['accuracy_exact']:.2%}  Soft={data['accuracy_soft']:.2%}"
            if "json_valid_rate" in data:
                line += (
                    f"  JSON(valid={data.get('json_valid_rate', 0):.2%}"
                    f", exact={data.get('json_exact_match', 0):.2%}"
                    f", extra={data.get('json_extra_field_rate', 0):.2%})"
                )
            if "semantic_similarity" in data:
                line += f"  Semantic Sim={data['semantic_similarity']:.2f}"
            if "similarity_bands" in data:
                b = data["similarity_bands"]
                line += f"  [correct≥0.8={b.get('correct',0):.2%} partial={b.get('partial',0):.2%} halluc<0.6={b.get('hallucination',0):.2%}]"
            print(line)
        else:
            print(f"  {key}: n={data['n']}  Refusal accuracy={data.get('refusal_rate', data.get('refusal_accuracy', 0)):.2%}  Hallucination rate={data.get('hallucination_rate', 0):.2%}")
    # Summary metrics table (Step 10)
    print("\n" + "-" * 60)
    print("SUMMARY METRICS")
    print("-" * 60)
    seen = results.get("seen", {})
    par = results.get("paraphrased", {})
    oos = results.get("out_of_scope", {})
    accuracy = 0.0
    if seen.get("n"):
        accuracy = seen.get("accuracy_exact", 0.0)
    if par.get("n") and accuracy == 0.0:
        accuracy = par.get("accuracy_exact", 0.0)
    if seen.get("n") and par.get("n"):
        accuracy = (seen.get("accuracy_exact", 0) * seen["n"] + par.get("accuracy_exact", 0) * par["n"]) / (seen["n"] + par["n"])
    sem_sim = seen.get("semantic_similarity") or par.get("semantic_similarity") or 0.0
    hall_rate = oos.get("hallucination_rate", 0.0)
    ref_acc = oos.get("refusal_rate") or oos.get("refusal_accuracy") or 0.0
    print(f"  {'Metric':<28} {'Score':>10}")
    print(f"  {'Exact Match (accuracy)':<28} {accuracy:>9.1%}")
    print(f"  {'Semantic similarity':<28} {sem_sim:>10.2f}")
    print(f"  {'Hallucination rate (OOS)':<28} {hall_rate:>9.1%}")
    print(f"  {'Refusal accuracy (OOS)':<28} {ref_acc:>9.1%}")
    print("=" * 60 + "\n")
