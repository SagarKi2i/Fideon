"""
Embedding pipeline.

Responsible for turning text chunks into vector embeddings for ChromaDB.
"""

from typing import Iterable, Dict, List


def embed_chunks(
    chunks: Iterable[Dict],
    model_name: str = "BAAI/bge-large-en",
) -> List[Dict]:
    """
    Placeholder for embedding logic.

    Each output record is expected to include:
    - all original chunk metadata
    - "embedding": list[float]
    """
    raise NotImplementedError("Embedding pipeline not implemented yet.")

