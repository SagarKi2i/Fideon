"""
Semantic caching with embedding-based similarity matching.
Ported from LLM Fallback 3.

Requires: pip install sentence-transformers numpy
Falls back gracefully when not installed.
"""

import logging
import importlib.util
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

SEMANTIC_AVAILABLE = (
    importlib.util.find_spec("sentence_transformers") is not None
    and importlib.util.find_spec("numpy") is not None
)

if not SEMANTIC_AVAILABLE:
    logger.info(
        "sentence-transformers/numpy not installed — semantic caching disabled. "
        "Install: pip install sentence-transformers numpy"
    )


class SemanticCacheManager:
    """
    Cosine-similarity matching for semantically equivalent queries.

    Example cache hits:
      "What is 2+2?"  →  "Calculate 2+2"
      "Capital of France?"  →  "What's the capital of France?"
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.85,
        persistence_backend: Any = None,
    ):
        if not SEMANTIC_AVAILABLE:
            raise ImportError(
                "sentence-transformers and numpy required. "
                "Install: pip install sentence-transformers numpy"
            )

        import numpy as np  # noqa: F401 – confirm import works
        from sentence_transformers import SentenceTransformer

        self.similarity_threshold = similarity_threshold
        self.embedding_index: List[Tuple[Any, str]] = []  # (np.ndarray, cache_key)
        self.backend = persistence_backend

        logger.info(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)

        # Restore index from persistence if available
        if self.backend and hasattr(self.backend, "get_all_embeddings"):
            try:
                loaded = self.backend.get_all_embeddings()
                self.embedding_index.extend(loaded)
                logger.info(f"Loaded {len(loaded)} semantic entries from persistence")
            except Exception as exc:
                logger.warning(f"Semantic index load failed: {exc}")

        logger.info(f"SemanticCacheManager ready (threshold={similarity_threshold})")

    # ------------------------------------------------------------------
    def get_embedding(self, text: str) -> Any:
        return self.model.encode(text, convert_to_numpy=True)

    def cosine_similarity(self, a: Any, b: Any) -> float:
        import numpy as np

        dot = float(np.dot(a, b))
        norm = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
        return dot / norm if norm != 0 else 0.0

    def find_similar(self, embedding: Any) -> Optional[Tuple[float, str]]:
        best_score = 0.0
        best_key: Optional[str] = None
        for cached_emb, key in self.embedding_index:
            score = self.cosine_similarity(embedding, cached_emb)
            if score > best_score:
                best_score, best_key = score, key
        if best_score >= self.similarity_threshold and best_key:
            logger.info(f"Semantic match: {best_score:.2%}")
            return (best_score, best_key)
        return None

    def add_to_index(self, embedding: Any, cache_key: str) -> None:
        self.embedding_index.append((embedding, cache_key))
        if self.backend and hasattr(self.backend, "save_embedding"):
            self.backend.save_embedding(cache_key, embedding)

    def get_stats(self) -> dict:
        return {
            "indexed_items": len(self.embedding_index),
            "similarity_threshold": self.similarity_threshold,
        }
