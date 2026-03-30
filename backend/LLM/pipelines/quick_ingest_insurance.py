"""
Quick ingestion script to build the `insurance_index` pgvector collection.

Usage (from backend directory, with venv activated):

    python -m LLM.pipelines.quick_ingest_insurance

It will:
- scan `LLM/data/insurance` for `.txt` files
- upsert chunks into the `insurance_index` collection in Postgres (pgvector)
- store one chunk per file (simple baseline; can be refined later)
"""

from pathlib import Path
from typing import List
import logging

from LLM.vectorstore.pgvector_store import Chunk, upsert_chunks


logger = logging.getLogger("fideon.ingest")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "insurance"
COLLECTION_NAME = "insurance_index"


def load_text_files() -> list[tuple[str, str]]:
    """
    Return a list of (doc_id, text) from .txt files in DATA_DIR.
    """
    docs: list[tuple[str, str]] = []
    if not DATA_DIR.exists():
        return docs

    for path in DATA_DIR.glob("**/*.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_id = path.stem
        cleaned = " ".join(text.split())
        if cleaned:
            docs.append((doc_id, cleaned))
    return docs


def _simple_chunks(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """
    Very simple word‑based sliding window chunking.
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


def main() -> None:
    texts = load_text_files()
    if not texts:
        logger.info(
            "Ingest[insurance] No .txt files found in %s. Nothing to ingest.", DATA_DIR
        )
        return

    records: List[Chunk] = []
    for doc_id, text in texts:
        chunks = _simple_chunks(text)
        if not chunks:
            continue
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}-chunk-{idx}"
            records.append(
                Chunk(
                    id=chunk_id,
                    text=chunk_text,
                    doc_id=doc_id,
                    chunk_index=idx,
                    metadata={"source": "insurance-txt"},
                )
            )
            logger.info(
                "Ingest[insurance] collection=%s doc_id=%s chunk_index=%d tokens~=%d",
                COLLECTION_NAME,
                doc_id,
                idx,
                len(chunk_text.split()),
            )

    if not records:
        logger.info(
            "Ingest[insurance] No chunks produced; nothing to write to pgvector."
        )
        return

    wrote = upsert_chunks(collection_name=COLLECTION_NAME, chunks=records)
    logger.info(
        "Ingest[insurance] Ingested %d chunks into collection '%s'.",
        wrote,
        COLLECTION_NAME,
    )


if __name__ == "__main__":
    main()

