"""
Abstract database repository interface.

All database backends (Supabase, MongoDB, Postgres, etc.) implement this.
Routes use DBRepository via Depends(get_db) — they never import a specific backend.

Switching DB = change DB_BACKEND env var. Nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Query DSL ─────────────────────────────────────────────────────────────────
# A DB-agnostic way to express queries. Each backend translates this to its
# own native format (PostgREST query string, pymongo filter dict, SQL WHERE, etc.)

@dataclass
class DBQuery:
    """
    Portable query descriptor understood by all repository implementations.

    Examples:
        # Simple equality filter
        DBQuery(filters={"user_id": uid, "tenant_id": tid})

        # Select specific columns, limit rows
        DBQuery(filters={"status": "active"}, select=["id", "name"], limit=10)

        # IN filter
        DBQuery(in_filters={"status": ["draft", "approved"]})

        # Combine
        DBQuery(
            filters={"tenant_id": tid},
            in_filters={"role": ["admin", "global_admin"]},
            select=["id", "role"],
            limit=1,
        )
    """
    # Equality filters: {"field": value}  →  field = value
    filters: Dict[str, Any] = field(default_factory=dict)

    # IN filters: {"field": [v1, v2]}  →  field IN (v1, v2)
    in_filters: Dict[str, List[Any]] = field(default_factory=dict)

    # Greater-than / less-than filters
    gt_filters: Dict[str, Any] = field(default_factory=dict)   # field > value
    lt_filters: Dict[str, Any] = field(default_factory=dict)   # field < value
    gte_filters: Dict[str, Any] = field(default_factory=dict)  # field >= value
    lte_filters: Dict[str, Any] = field(default_factory=dict)  # field <= value

    # Columns to return (empty list = all columns)
    select: List[str] = field(default_factory=list)

    # Ordering: field name; prefix with "-" for descending  e.g. "-created_at"
    order_by: Optional[str] = None

    # Row limit (None = no limit)
    limit: Optional[int] = None

    # Offset for pagination
    offset: Optional[int] = None


# ── Abstract Repository ────────────────────────────────────────────────────────

class DBRepository(ABC):
    """
    Abstract interface for all database operations.

    Implementations:
        SupabaseRepository  — Supabase PostgREST (current / default)
        MongoRepository     — MongoDB via motor (stub)
        PostgresRepository  — Direct PostgreSQL via asyncpg (stub)

    Do NOT import a specific implementation in route files.
    Always use: db: DBRepository = Depends(get_db)
    """

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get(self, table: str, query: DBQuery) -> List[Dict[str, Any]]:
        """Fetch zero or more rows matching query."""
        ...

    @abstractmethod
    async def get_one(self, table: str, query: DBQuery) -> Optional[Dict[str, Any]]:
        """Fetch exactly one row or None."""
        ...

    @abstractmethod
    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one row. Returns the inserted row."""
        ...

    @abstractmethod
    async def insert_many(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple rows. Returns inserted rows."""
        ...

    @abstractmethod
    async def update(self, table: str, query: DBQuery, data: Dict[str, Any]) -> None:
        """Update rows matching query with data."""
        ...

    @abstractmethod
    async def delete(self, table: str, query: DBQuery) -> None:
        """Delete rows matching query."""
        ...

    @abstractmethod
    async def count(self, table: str, query: DBQuery) -> int:
        """Return count of rows matching query."""
        ...

    # ── Auth ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def verify_user(self, token: str) -> Dict[str, Any]:
        """
        Validate a Bearer JWT and return the user object.
        Raises HTTPException 401 on invalid token.
        """
        ...

    @abstractmethod
    async def admin_list_users(self) -> List[Dict[str, Any]]:
        """Return all users (admin-level operation)."""
        ...

    # ── Tenant-scoped convenience ─────────────────────────────────────────────

    async def tenant_get(
        self,
        table: str,
        query: DBQuery,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """get() with tenant_id automatically injected into filters."""
        scoped = DBQuery(
            filters={**query.filters, "tenant_id": tenant_id},
            in_filters=query.in_filters,
            gt_filters=query.gt_filters,
            lt_filters=query.lt_filters,
            gte_filters=query.gte_filters,
            lte_filters=query.lte_filters,
            select=query.select,
            order_by=query.order_by,
            limit=query.limit,
            offset=query.offset,
        )
        return await self.get(table, scoped)

    async def tenant_insert(
        self,
        table: str,
        data: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """insert() with tenant_id automatically injected into data."""
        return await self.insert(table, {**data, "tenant_id": tenant_id})

    async def tenant_update(
        self,
        table: str,
        query: DBQuery,
        data: Dict[str, Any],
        tenant_id: str,
    ) -> None:
        """update() with tenant_id automatically injected into filters."""
        scoped = DBQuery(
            filters={**query.filters, "tenant_id": tenant_id},
            in_filters=query.in_filters,
            select=query.select,
            limit=query.limit,
        )
        return await self.update(table, scoped, data)
