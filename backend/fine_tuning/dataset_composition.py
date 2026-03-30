"""
Dataset composition for QLoRA: 70% document QA, 20% paraphrased QA, 10% refusal examples.

Reduces hallucination by training the model to refuse out-of-scope questions.
Run after pdf_to_dataset (or use your own doc QA JSON), then pass the output as dataset_path for training.

Usage:
  python -m fine_tuning.dataset_composition --doc-qa fine_tuning/dataset.json --output fine_tuning/dataset_mixed.json
  python -m fine_tuning.dataset_composition --doc-qa dataset.json --refusal-ratio 0.1 --output dataset_mixed.json
"""

from pathlib import Path
import argparse
import json
import random
from typing import Any, Dict, List, Optional

# Default refusal examples (out-of-scope questions → correct refusal response)
DEFAULT_REFUSAL_EXAMPLES = [
    {"instruction": "What is the capital of France?", "input": "", "output": "This question is outside the scope of the document."},
    {"instruction": "Who won the World Cup in 2022?", "input": "", "output": "This information is not found in the document."},
    {"instruction": "What is the weather today?", "input": "", "output": "This question is unrelated to the document."},
    {"instruction": "Explain quantum physics.", "input": "", "output": "This topic is not covered in the document."},
    {"instruction": "What is the stock price of Apple?", "input": "", "output": "This information is not present in the document."},
    {"instruction": "Who wrote Hamlet?", "input": "", "output": "This question is outside the scope of the document."},
    {"instruction": "How do I cook pasta?", "input": "", "output": "This question is unrelated to the document."},
    {"instruction": "What is the population of India?", "input": "", "output": "This information is not found in the document."},
    {"instruction": "Describe the plot of Star Wars.", "input": "", "output": "This topic is not covered in the document."},
    {"instruction": "What is 2 + 2?", "input": "", "output": "This question is outside the scope of the document."},
]


def load_json(path: Path) -> List[Dict[str, Any]]:
    """Load JSON array from file."""
    text = path.read_text(encoding="utf-8").strip()
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return [data]


def save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    """Save list of examples to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_example(ex: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure instruction, input, output keys; drop extra keys for training."""
    return {
        "instruction": ex.get("instruction", ""),
        "input": ex.get("input", ""),
        "output": ex.get("output", ""),
    }


def build_paraphrased_from_doc_qa(doc_qa: List[Dict[str, Any]], ratio: float) -> List[Dict[str, Any]]:
    """
    Create paraphrased examples by rephrasing instructions (simple variants).
    Uses a fixed set of instruction prefixes to simulate paraphrased questions.
    """
    if ratio <= 0 or not doc_qa:
        return []
    n = max(1, int(len(doc_qa) * ratio))
    # Sample and create paraphrased versions with alternative phrasings
    paraphrased_templates = [
        ("Explain: ", ""),
        ("Can you describe: ", ""),
        ("What does the document say about: ", " (Summarize briefly.)"),
    ]
    out = []
    indices = random.sample(range(len(doc_qa)), min(n, len(doc_qa)))
    for i in indices:
        ex = doc_qa[i]
        inst = ex.get("instruction", "")
        # Simple paraphrase: use first few words as "topic" with different wrapper
        words = inst.replace("?", "").strip().split()[:5]
        topic = " ".join(words) if words else inst
        for prefix, suffix in paraphrased_templates[:1]:  # one paraphrase per sampled example
            new_inst = f"{prefix}{topic}?{suffix}".strip()
            if new_inst != inst:
                out.append(normalize_example({
                    "instruction": new_inst,
                    "input": ex.get("input", ""),
                    "output": ex.get("output", ""),
                }))
            if len(out) >= n:
                break
        if len(out) >= n:
            break
    return out[:n]


def compose_dataset(
    doc_qa_path: Path,
    output_path: Path,
    *,
    doc_qa_ratio: float = 0.70,
    paraphrased_ratio: float = 0.20,
    refusal_ratio: float = 0.10,
    refusal_examples_path: Optional[Path] = None,
    paraphrased_path: Optional[Path] = None,
    seed: int = 42,
) -> int:
    """
    Build mixed dataset: doc_qa_ratio (document QA) + paraphrased_ratio (paraphrased) + refusal_ratio (refusal).
    Ratios should sum to 1.0.
    """
    random.seed(seed)
    doc_qa = load_json(doc_qa_path)
    doc_qa = [normalize_example(ex) for ex in doc_qa]
    if not doc_qa:
        raise ValueError(f"No document QA examples in {doc_qa_path}")

    total_target = len(doc_qa)  # keep same total size, just rebalance
    n_doc = max(1, int(total_target * doc_qa_ratio))
    n_paraphrased = max(0, int(total_target * paraphrased_ratio))
    n_refusal = max(0, int(total_target * refusal_ratio))

    # Document QA: use all if we need more than we have, else sample
    if n_doc >= len(doc_qa):
        selected_doc = doc_qa
    else:
        selected_doc = random.sample(doc_qa, n_doc)

    # Paraphrased: from file or generate from doc_qa
    if paraphrased_path and paraphrased_path.exists():
        paraphrased = load_json(paraphrased_path)
        paraphrased = [normalize_example(ex) for ex in paraphrased][:n_paraphrased]
    else:
        paraphrased = build_paraphrased_from_doc_qa(doc_qa, paraphrased_ratio)[:n_paraphrased]

    # Refusal: from file or use defaults
    if refusal_examples_path and refusal_examples_path.exists():
        refusal = load_json(refusal_examples_path)
        refusal = [normalize_example(ex) for ex in refusal]
    else:
        refusal = [normalize_example(ex) for ex in DEFAULT_REFUSAL_EXAMPLES]
    # Sample to reach n_refusal
    if len(refusal) >= n_refusal:
        refusal = random.sample(refusal, n_refusal)
    else:
        # Repeat if we need more
        while len(refusal) < n_refusal:
            refusal.extend(random.sample(refusal, min(n_refusal - len(refusal), len(refusal))))

    combined = selected_doc + paraphrased + refusal
    random.shuffle(combined)
    save_json(output_path, combined)
    return len(combined)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose training dataset: 70% doc QA, 20% paraphrased, 10% refusal"
    )
    parser.add_argument("--doc-qa", "-d", required=True, help="Path to document QA JSON (e.g. from pdf_to_dataset)")
    parser.add_argument("--output", "-o", required=True, help="Output JSON path")
    parser.add_argument("--doc-qa-ratio", type=float, default=0.70)
    parser.add_argument("--paraphrased-ratio", type=float, default=0.20)
    parser.add_argument("--refusal-ratio", type=float, default=0.10)
    parser.add_argument("--refusal-examples", default=None, help="Optional JSON with refusal examples")
    parser.add_argument("--paraphrased", default=None, help="Optional JSON with paraphrased QA")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_path = Path(args.output)
    doc_qa_path = Path(args.doc_qa)
    refusal_path = Path(args.refusal_examples) if args.refusal_examples else None
    paraphrased_path = Path(args.paraphrased) if args.paraphrased else None

    n = compose_dataset(
        doc_qa_path,
        output_path,
        doc_qa_ratio=args.doc_qa_ratio,
        paraphrased_ratio=args.paraphrased_ratio,
        refusal_ratio=args.refusal_ratio,
        refusal_examples_path=refusal_path,
        paraphrased_path=paraphrased_path,
        seed=args.seed,
    )
    print(f"Wrote {n} examples to {output_path} (doc_qa ~{args.doc_qa_ratio:.0%}, paraphrased ~{args.paraphrased_ratio:.0%}, refusal ~{args.refusal_ratio:.0%})")


if __name__ == "__main__":
    main()
