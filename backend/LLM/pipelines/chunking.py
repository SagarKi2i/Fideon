"""
Chunking pipeline.

Implements sliding-window chunking over page-level text with overlap.
"""

from typing import Iterable, Dict, List


def sliding_window_chunks(
    pages: Iterable[Dict],
    chunk_size_tokens: int = 512,
    overlap_tokens: int = 50,
) -> List[Dict]:
    """
    Placeholder for chunking logic.

    Each output record is expected to include:
    - doc_id, page, section
    - chunk_index, text
    """
    raise NotImplementedError("Chunking pipeline not implemented yet.")

