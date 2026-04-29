"""
Direct PostgreSQL implementation of DBRepository — STUB.

Use this when you want to connect directly to PostgreSQL (any provider —
AWS RDS, Azure Database, self-hosted) without going through Supabase's
PostgREST HTTP layer.

Dependencies to add to requirements.txt when implementing:
    asyncpg>=0.29.0       # async PostgreSQL driver (fastest)
    # OR
    psycopg[binary]>=3.1.0  # already in requirements.txt — psycopg3

Environment variables needed:
    POSTGRES_DSN=postgresql://user:pass@host:5432/dbname
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.db.base import DBQuery, DBRepository


class PostgresRepository(DBRepository):
    """
    Direct PostgreSQL implementation via asyncpg.
    NOT implemented yet — raises NotImplementedError on all methods.

    To implement:
      1. pip install asyncpg>=0.29.0
      2. Add POSTGRES_DSN to .env
      3. Replace NotImplementedError with asyncpg calls below.
         Each DBQuery filter maps to a SQL WHERE clause:
           DBQuery(filters={"user_id": uid}) → WHERE user_id = $1
           DBQuery(in_filters={"role": ["admin","user"]}) → WHERE role = ANY($1)
           DBQuery(gt_filters={"created_at": ts}) → WHERE created_at > $1

    Note on RLS:
        Unlike Supabase (which enforces RLS via JWT claims), direct Postgres
        connections use a service role that bypasses RLS by default.
        You MUST enforce tenant_id filters at the application layer using
        tenant_get() / tenant_insert() / tenant_update() from DBRepository.
    """

    def __init__(self) -> None:
        # When implementing: initialise asyncpg pool here.
        # import asyncpg
        # self._pool = None  (create in an async init method or lifespan)
        pass

    def _build_where(self, query: DBQuery) -> tuple[str, list]:
        """
        Build SQL WHERE clause and params list from DBQuery.
        Returns (where_clause, params) where params is a list of values for $1..$N.
        """
        clauses: list[str] = []
        params: list[Any] = []
        idx = 1

        for field, value in query.filters.items():
            if value is None:
                clauses.append(f"{field} IS NULL")
            else:
                clauses.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        for field, values in query.in_filters.items():
            clauses.append(f"{field} = ANY(${idx})")
            params.append(values)
            idx += 1

        for field, value in query.gt_filters.items():
            clauses.append(f"{field} > ${idx}")
            params.append(value)
            idx += 1

        for field, value in query.lt_filters.items():
            clauses.append(f"{field} < ${idx}")
            params.append(value)
            idx += 1

        for field, value in query.gte_filters.items():
            clauses.append(f"{field} >= ${idx}")
            params.append(value)
            idx += 1

        for field, value in query.lte_filters.items():
            clauses.append(f"{field} <= ${idx}")
            params.append(value)
            idx += 1

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def get(self, table: str, query: DBQuery) -> List[Dict[str, Any]]:
        raise NotImplementedError("PostgresRepository.get not implemented")
        # When implementing:
        # cols = ", ".join(query.select) if query.select else "*"
        # where, params = self._build_where(query)
        # order = f"ORDER BY {query.order_by.lstrip('-')} {'DESC' if query.order_by.startswith('-') else 'ASC'}" if query.order_by else ""
        # limit = f"LIMIT {query.limit}" if query.limit else ""
        # offset = f"OFFSET {query.offset}" if query.offset else ""
        # sql = f"SELECT {cols} FROM {table} {where} {order} {limit} {offset}"
        # rows = await self._pool.fetch(sql, *params)
        # return [dict(r) for r in rows]

    async def get_one(self, table: str, query: DBQuery) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("PostgresRepository.get_one not implemented")

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("PostgresRepository.insert not implemented")
        # cols = ", ".join(data.keys())
        # placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        # sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *"
        # row = await self._pool.fetchrow(sql, *data.values())
        # return dict(row)

    async def insert_many(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError("PostgresRepository.insert_many not implemented")

    async def update(self, table: str, query: DBQuery, data: Dict[str, Any]) -> None:
        raise NotImplementedError("PostgresRepository.update not implemented")

    async def delete(self, table: str, query: DBQuery) -> None:
        raise NotImplementedError("PostgresRepository.delete not implemented")

    async def count(self, table: str, query: DBQuery) -> int:
        raise NotImplementedError("PostgresRepository.count not implemented")

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def verify_user(self, token: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "PostgresRepository.verify_user not implemented. "
            "Direct Postgres has no auth service. "
            "Use PyJWT to verify tokens issued by your auth provider."
        )

    async def admin_list_users(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("PostgresRepository.admin_list_users not implemented")
