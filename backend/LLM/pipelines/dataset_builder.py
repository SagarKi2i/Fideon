"""
Training dataset builder.

Takes retrieved chunks and generates instruction-style QA pairs
for supervised fine-tuning / SFT with LoRA.
"""

from typing import Iterable, Dict, List


def build_qa_dataset(
    chunks: Iterable[Dict],
    *,
    domain: str,
) -> List[Dict]:
    """
    Placeholder for dataset construction logic.

    Expected output format per sample:
    {
        "instruction": str,
        "context": str,
        "output": str,
        "domain": str,
    }
    """
    raise NotImplementedError("Dataset builder not implemented yet.")

