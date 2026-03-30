"""
Document ingestion pipeline.

Responsibilities:
- Load raw domain documents (PDF, DOC, HTML, APIs).
- Normalize and clean text.
- Produce per-page records ready for chunking.
"""

from pathlib import Path
from typing import Iterable


def ingest_documents(source_dir: Path) -> Iterable[dict]:
    """
    Placeholder signature for the ingestion pipeline.

    Expected to yield records like:
    {
        "doc_id": str,
        "page": int,
        "section": str | None,
        "text": str,
        "domain": str,
    }
    """
    raise NotImplementedError("Ingestion pipeline not implemented yet.")

