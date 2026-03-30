from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from LLM.vectorstore.pgvector_store import Chunk, upsert_chunks

logger = logging.getLogger("fideon.vectorstore.ingestion")


def _fail_open_enabled() -> bool:
    return (os.getenv("PGVECTOR_INGEST_FAIL_OPEN", "true").strip().lower() in {"1", "true", "yes", "on"})


def _simple_chunks(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """
    Same word-based sliding window chunking used by ACORD ingestion.
    """
    words = text.split()
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


def ingest_text_into_vectorstore(
    *,
    collection_name: str,
    doc_id: str,
    text: str,
    pod_id: Optional[str] = None,
    source: str = "pod-upload",
) -> int:
    """
    Persist text into pgvector store so RAG can retrieve it later.
    """
    chunks = _simple_chunks(text)
    if not chunks:
        return 0

    records: List[Chunk] = []
    for idx, chunk_text in enumerate(chunks):
        chunk_id = f"{doc_id}-chunk-{idx}"
        metadata: Dict[str, Any] = {"source": source}
        if pod_id:
            metadata["pod_id"] = pod_id
        records.append(
            Chunk(
                id=chunk_id,
                text=chunk_text,
                doc_id=doc_id,
                chunk_index=idx,
                metadata=metadata,
            )
        )

    try:
        return upsert_chunks(collection_name=collection_name, chunks=records)
    except Exception as exc:
        if not _fail_open_enabled():
            raise
        msg = str(exc)
        logger.warning(
            "Vector ingest skipped (fail-open): collection=%s doc_id=%s reason=%s",
            collection_name,
            doc_id,
            msg[:300],
        )
        return 0

