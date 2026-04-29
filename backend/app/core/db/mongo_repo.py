"""
MongoDB implementation of DBRepository — STUB.

Fill this in when you want to switch to MongoDB.

Dependencies to add to requirements.txt when implementing:
    motor>=3.3.0          # async MongoDB driver
    pymongo>=4.6.0        # sync driver (motor depends on it)

Environment variables needed:
    MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/fideon
    MONGODB_DB=fideon
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.db.base import DBQuery, DBRepository


class MongoRepository(DBRepository):
    """
    MongoDB implementation via motor (async driver).
    NOT implemented yet — raises NotImplementedError on all methods.

    To implement:
      1. pip install motor>=3.3.0
      2. Add MONGODB_URI and MONGODB_DB to .env
      3. Replace NotImplementedError with motor collection calls below.
         Each DBQuery filter maps to a pymongo filter dict:
           DBQuery(filters={"user_id": uid}) → {"user_id": uid}
           DBQuery(in_filters={"role": ["admin","user"]}) → {"role": {"$in": ["admin","user"]}}
           DBQuery(gt_filters={"created_at": ts}) → {"created_at": {"$gt": ts}}
    """

    def __init__(self) -> None:
        # When implementing: initialise motor client here.
        # import motor.motor_asyncio
        # self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        # self._db = self._client[MONGODB_DB]
        pass

    def _col(self, table: str):  # type: ignore[return]
        """Return the motor collection for the given table name."""
        raise NotImplementedError("MongoDB not configured — set DB_BACKEND=mongodb and implement MongoRepository")

    def _to_filter(self, query: DBQuery) -> dict:
        """Translate DBQuery to a pymongo filter dict."""
        f: dict = {}
        for field, value in query.filters.items():
            f[field] = value
        for field, values in query.in_filters.items():
            f[field] = {"$in": values}
        for field, value in query.gt_filters.items():
            f.setdefault(field, {})["$gt"] = value
        for field, value in query.lt_filters.items():
            f.setdefault(field, {})["$lt"] = value
        for field, value in query.gte_filters.items():
            f.setdefault(field, {})["$gte"] = value
        for field, value in query.lte_filters.items():
            f.setdefault(field, {})["$lte"] = value
        return f

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def get(self, table: str, query: DBQuery) -> List[Dict[str, Any]]:
        raise NotImplementedError("MongoRepository.get not implemented")
        # When implementing:
        # col = self._col(table)
        # cursor = col.find(self._to_filter(query))
        # if query.order_by:
        #     col_name = query.order_by.lstrip("-")
        #     direction = -1 if query.order_by.startswith("-") else 1
        #     cursor = cursor.sort(col_name, direction)
        # if query.limit:
        #     cursor = cursor.limit(query.limit)
        # if query.offset:
        #     cursor = cursor.skip(query.offset)
        # return await cursor.to_list(length=query.limit or 1000)

    async def get_one(self, table: str, query: DBQuery) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("MongoRepository.get_one not implemented")
        # col = self._col(table)
        # return await col.find_one(self._to_filter(query))

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("MongoRepository.insert not implemented")
        # col = self._col(table)
        # result = await col.insert_one(data)
        # return {**data, "_id": str(result.inserted_id)}

    async def insert_many(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError("MongoRepository.insert_many not implemented")

    async def update(self, table: str, query: DBQuery, data: Dict[str, Any]) -> None:
        raise NotImplementedError("MongoRepository.update not implemented")
        # col = self._col(table)
        # await col.update_many(self._to_filter(query), {"$set": data})

    async def delete(self, table: str, query: DBQuery) -> None:
        raise NotImplementedError("MongoRepository.delete not implemented")
        # col = self._col(table)
        # await col.delete_many(self._to_filter(query))

    async def count(self, table: str, query: DBQuery) -> int:
        raise NotImplementedError("MongoRepository.count not implemented")
        # col = self._col(table)
        # return await col.count_documents(self._to_filter(query))

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def verify_user(self, token: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "MongoRepository.verify_user not implemented. "
            "MongoDB has no built-in auth service. "
            "Use Auth0, Firebase Auth, or a custom JWT validator."
        )

    async def admin_list_users(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("MongoRepository.admin_list_users not implemented")
