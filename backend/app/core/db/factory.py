"""
DB backend factory.

Reads DB_BACKEND env var and returns the correct DBRepository implementation.
Switching database = change one env var. Nothing else changes.

Supported values:
    supabase  (default) — Supabase PostgREST + GoTrue
    mongodb             — MongoDB via motor (stub — implement MongoRepository first)
    postgres            — Direct PostgreSQL via asyncpg (stub — implement PostgresRepository first)

Usage:
    # In deps.py (FastAPI Depends):
    from app.core.db.factory import get_repository
    def get_db() -> DBRepository:
        return get_repository()

    # In a route:
    @router.get("/devices")
    async def list_devices(db: DBRepository = Depends(get_db)):
        rows = await db.tenant_get("devices", DBQuery(), tenant_id=ctx["tenant_id"])
        return rows
"""

from __future__ import annotations

import os

from app.core.db.base import DBRepository

# Singleton instances — one per process (repositories are stateless).
_instances: dict[str, DBRepository] = {}


def get_repository() -> DBRepository:
    """
    Return the active DBRepository implementation based on DB_BACKEND env var.
    Instances are cached (created once per process lifetime).
    """
    backend = (os.getenv("DB_BACKEND") or "supabase").strip().lower()

    if backend not in _instances:
        _instances[backend] = _create(backend)

    return _instances[backend]


def _create(backend: str) -> DBRepository:
    if backend == "supabase":
        from app.core.db.supabase_repo import SupabaseRepository
        return SupabaseRepository()

    if backend == "mongodb":
        from app.core.db.mongo_repo import MongoRepository
        return MongoRepository()

    if backend in ("postgres", "postgresql"):
        from app.core.db.postgres_repo import PostgresRepository
        return PostgresRepository()

    raise ValueError(
        f"Unknown DB_BACKEND='{backend}'. "
        f"Supported values: supabase, mongodb, postgres"
    )
