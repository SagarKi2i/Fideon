"""
DB abstraction layer — Repository Pattern.

Public API:
    from app.core.db import DBRepository, DBQuery, get_db

    # In a route:
    @router.get("/items")
    async def list_items(db: DBRepository = Depends(get_db)):
        return await db.tenant_get("items", DBQuery(limit=50), tenant_id=tid)
"""

from app.core.db.base import DBQuery, DBRepository
from app.core.db.factory import get_repository


def get_db() -> DBRepository:
    """FastAPI Depends() callable — returns the active repository."""
    return get_repository()


__all__ = ["DBRepository", "DBQuery", "get_db"]
