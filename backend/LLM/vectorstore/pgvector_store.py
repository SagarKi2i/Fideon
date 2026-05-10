from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import psycopg
from pgvector.psycopg import register_vector


logger = logging.getLogger("fideon.pgvector")

_embedder: Any | None = None


def _load_backend_env_file() -> None:
    """
    Ensure pgvector reads backend/.env in local runs where process env is sparse.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (key not in os.environ or not str(os.environ.get(key, "")).strip()):
            os.environ[key] = value


_load_backend_env_file()


def _get_embedder(model_name: str = "BAAI/bge-large-en") -> Any:
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer  # lazy import — not in docker image
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed in this environment. "
                "Add it to requirements.txt or install it manually."
            ) from exc
        # Try local cache only first to avoid blocking on a slow / absent internet
        # connection.  If the model is not cached yet, fall back to a download but
        # only when the user has explicitly allowed it via env var.
        try:
            _embedder = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            allow_download = os.getenv("ALLOW_EMBEDDER_DOWNLOAD", "false").strip().lower()
            if allow_download not in ("1", "true", "yes"):
                raise RuntimeError(
                    f"Embedding model '{model_name}' is not cached locally and "
                    "ALLOW_EMBEDDER_DOWNLOAD is not set to 'true'. "
                    "To pre-download it, run: "
                    f"python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('{model_name}')\" "
                    "or set ALLOW_EMBEDDER_DOWNLOAD=true to allow downloading at runtime."
                )
            logger.warning("Embedding model '%s' not in local cache; downloading now (this may take a while).", model_name)
            _embedder = SentenceTransformer(model_name)
    return _embedder


def _db_url() -> str:
    # Prefer explicit PGVECTOR_DATABASE_URL, fallback to common DATABASE_URL.
    return (os.getenv("PGVECTOR_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


def _db_url_source() -> str:
    if (os.getenv("PGVECTOR_DATABASE_URL") or "").strip():
        return "PGVECTOR_DATABASE_URL"
    if (os.getenv("DATABASE_URL") or "").strip():
        return "DATABASE_URL"
    return "unset"


def _safe_conn_signature(url: str) -> str:
    try:
        parsed = urlparse(url)
        user = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or ""
        db = (parsed.path or "/").lstrip("/")
        return f"user={user} host={host} port={port} db={db}"
    except Exception:
        return "unparseable-connection-url"


def _table_name() -> str:
    return (os.getenv("PGVECTOR_TABLE") or "rag_chunks").strip()


def _connect() -> psycopg.Connection:
    url = _db_url()
    if not url:
        raise RuntimeError("PGVECTOR_DATABASE_URL (or DATABASE_URL) is not configured")
    # Avoid hanging indefinitely on misconfigured URLs/network issues.
    try:
        conn = psycopg.connect(url, autocommit=True, connect_timeout=10)
        register_vector(conn)
        return conn
    except Exception as exc:
        msg = str(exc)
        logger.error(
            "PGVECTOR connect failed (%s): %s | source=%s",
            _safe_conn_signature(url),
            msg[:500],
            _db_url_source(),
        )
        if "Tenant or user not found" in msg:
            logger.error(
                "PGVECTOR credential/tenant mismatch. Verify project-ref username and password in %s.",
                _db_url_source(),
            )
        raise


def ensure_schema(vector_dim: int = 1024) -> None:
    """
    Ensure pgvector extension + storage table exist.
    Adds tenant_id column if missing (safe to run on existing tables).
    We store normalized embeddings for cosine distance queries.
    """
    table = _table_name()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    collection_name TEXT NOT NULL,
                    tenant_id TEXT,
                    doc_id TEXT,
                    chunk_index INTEGER,
                    text TEXT NOT NULL,
                    embedding vector({vector_dim}) NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            # C2: Add tenant_id to existing tables that pre-date this migration.
            cur.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS tenant_id TEXT;
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_collection_idx ON {table} (collection_name);"
            )
            # C2: Composite index for tenant-scoped similarity searches.
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_tenant_collection_idx "
                f"ON {table} (tenant_id, collection_name);"
            )


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    doc_id: Optional[str] = None
    chunk_index: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


def upsert_chunks(
    *,
    collection_name: str,
    chunks: Iterable[Chunk],
    embedding_model: str = "BAAI/bge-large-en",
    tenant_id: Optional[str] = None,   # C2: required for multi-tenant safety
) -> int:
    """
    Compute embeddings and upsert chunks into pgvector store.

    C2 — tenant_id:
        Always pass tenant_id when calling from a request context.
        Rows without tenant_id are only acceptable for system-level ingestion
        (e.g., seed data, shared catalogs).
        Logged to comply with pgvector audit requirements.
    """
    if not tenant_id:
        logger.warning(
            "upsert_chunks called WITHOUT tenant_id for collection '%s'. "
            "All rows will have tenant_id=NULL — ensure this is intentional "
            "(e.g., shared catalog ingestion).",
            collection_name,
        )

    chunk_list = list(chunks)
    if not chunk_list:
        return 0

    # Fail fast on DB connectivity before loading/downloading embedding weights.
    ensure_schema(vector_dim=1024)
    table = _table_name()

    embedder = _get_embedder(embedding_model)
    texts = [c.text for c in chunk_list]
    vectors = embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    rows: List[tuple] = []
    for i, c in enumerate(chunk_list):
        md = c.metadata or {}
        md = {"collection_name": collection_name, **md}
        rows.append(
            (
                c.id,
                collection_name,
                tenant_id,          # C2: stored per-row
                c.doc_id,
                c.chunk_index,
                c.text,
                vectors[i].tolist(),
                json.dumps(md),
            )
        )

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO {table}
                    (id, collection_name, tenant_id, doc_id, chunk_index, text, embedding, metadata)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    collection_name = EXCLUDED.collection_name,
                    tenant_id       = EXCLUDED.tenant_id,
                    doc_id          = EXCLUDED.doc_id,
                    chunk_index     = EXCLUDED.chunk_index,
                    text            = EXCLUDED.text,
                    embedding       = EXCLUDED.embedding,
                    metadata        = EXCLUDED.metadata,
                    updated_at      = now()
                ;
                """,
                rows,
            )

    # C2: Audit log for compliance trail on vector writes.
    logger.info(
        "pgvector.upsert tenant=%s collection=%s chunks=%d",
        tenant_id or "NULL",
        collection_name,
        len(rows),
    )
    return len(rows)


def query_similar(
    *,
    collection_name: str,
    query: str,
    k: int = 10,
    embedding_model: str = "BAAI/bge-large-en",
    tenant_id: Optional[str] = None,   # C2: required for multi-tenant safety
) -> List[Dict[str, Any]]:
    """
    Return top-k chunks ordered by cosine distance (lower is better).

    C2 — tenant_id:
        Always pass tenant_id when calling from a request context.
        Without it, the query searches ALL tenants' chunks — a security risk.
        A warning is emitted and results are filtered to tenant_id IS NULL
        (shared/system chunks only) when tenant_id is not provided.
    """
    if not tenant_id:
        logger.warning(
            "query_similar called WITHOUT tenant_id for collection '%s'. "
            "Restricting to tenant_id IS NULL rows only.",
            collection_name,
        )

    embedder = _get_embedder(embedding_model)
    qvec = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]

    ensure_schema(vector_dim=int(qvec.shape[0]))
    table = _table_name()

    # C2: Always scope by tenant_id. When tenant_id is provided, return only
    # that tenant's chunks. When absent, return only shared (NULL) chunks.
    if tenant_id:
        tenant_filter = "AND (tenant_id = %s OR tenant_id IS NULL)"
        filter_params = (qvec.tolist(), collection_name, tenant_id, qvec.tolist(), k)
    else:
        tenant_filter = "AND tenant_id IS NULL"
        filter_params = (qvec.tolist(), collection_name, qvec.tolist(), k)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, doc_id, chunk_index, text, metadata, (embedding <=> %s) AS distance
                FROM {table}
                WHERE collection_name = %s
                {tenant_filter}
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                filter_params,
            )
            rows = cur.fetchall()

    # C2: Audit log for compliance trail on vector reads.
    logger.info(
        "pgvector.query tenant=%s collection=%s results=%d",
        tenant_id or "NULL",
        collection_name,
        len(rows),
    )

    out: List[Dict[str, Any]] = []
    for (cid, doc_id, chunk_index, text, metadata, distance) in rows:
        meta = metadata or {}
        out.append(
            {
                "id": cid,
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "text": text,
                "score": float(1.0 - float(distance)),
                **(meta if isinstance(meta, dict) else {}),
            }
        )
    return out

