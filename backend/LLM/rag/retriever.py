"""
RAG retriever.

Responsible for:
- Selecting the correct vector store collection per domain / agent.
- Running vector similarity search.
- Returning top‑K chunks with metadata.
"""

from __future__ import annotations

import logging
from typing import List, Dict

import numpy as np
from sentence_transformers import SentenceTransformer

from LLM.vectorstore import pgvector_store

logger = logging.getLogger("fideon.rag")
_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("BAAI/bge-large-en")
    return _embedding_model


def retrieve(
    query: str,
    *,
    collection_name: str,
    k: int = 10,
) -> List[Dict]:
    """
    Retrieve top‑K similar chunks from the given pgvector collection.
    """
    logger.info("RAG[store] query='%s' collection=%s k=%d", query[:80], collection_name, k)
    results = pgvector_store.query_similar(
        collection_name=collection_name,
        query=query,
        k=k,
    )

    output: List[Dict] = []
    for record in results:
        chunk_id = record.get("id")
        doc_id = record.get("doc_id")
        chunk_index = record.get("chunk_index")
        logger.info(
            "RAG[store] hit id=%s doc_id=%s chunk_index=%s",
            chunk_id,
            doc_id,
            chunk_index,
        )
        output.append(record)
    return output


def retrieve_from_documents(
    query: str,
    documents: List[Dict],
    k: int = 10,
) -> List[Dict]:
    """
    In‑memory retrieval over a small set of user‑provided documents.

    Each document is expected to have:
    - "id": str
    - "text": str
    """
    docs_with_text = [d for d in documents if d.get("text")]
    if not docs_with_text:
        return []

    model = _get_embedding_model()
    texts = [d["text"] for d in docs_with_text]

    embeddings = model.encode(
        [query] + texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    query_vec = embeddings[0]
    doc_vecs = embeddings[1:]

    scores = np.dot(doc_vecs, query_vec)
    top_indices = np.argsort(-scores)[:k]

    results: List[Dict] = []
    for idx in top_indices:
        doc = docs_with_text[int(idx)]
        record = (
            {
                "id": doc.get("id"),
                "doc_id": doc.get("id"),
                "page": 1,
                "text": doc.get("text", ""),
                "score": float(scores[int(idx)]),
            }
        )
        print(
            f"[rag] in-memory doc retrieval "
            f"doc_id={record['doc_id']} score={record['score']:.4f}"
        )
        results.append(record)
    return results

