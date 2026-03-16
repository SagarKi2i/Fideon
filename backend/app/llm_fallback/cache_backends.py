"""
Cache backend implementations for LLM Fallback Service.
Ported from LLM Fallback 3.

Backends:
  local   – in-memory + JSON disk file (zero dependencies, default)
  redis   – requires: pip install redis
  momento – requires: pip install momento
"""

import json
import os
import time
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from .models import CacheEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    from momento import CacheClient, Configurations, CredentialProvider
    from momento.responses import CacheGet, CacheSet, CreateCache
    _MOMENTO_AVAILABLE = True
except ImportError:
    _MOMENTO_AVAILABLE = False

try:
    import redis as _redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Local (in-memory + disk persistence)
# ---------------------------------------------------------------------------

class LocalMemoryCache:
    """
    Zero-dependency in-memory cache with JSON disk persistence.
    All entries are permanent (no TTL expiry).
    """

    def __init__(self, cache_ttl: int = 3_600_000, cache_file: str = "llm_cache_local.json"):
        self.cache: Dict[str, CacheEntry] = {}
        self.permanent_cache: Dict[str, CacheEntry] = {}
        self.cache_file = cache_file
        self._load_from_disk()
        logger.info(f"LocalMemoryCache ready ({cache_file})")

    # ------------------------------------------------------------------
    def _load_from_disk(self) -> None:
        if not os.path.exists(self.cache_file):
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for k, v in data.get("cache", {}).items():
                self.cache[k] = CacheEntry.from_dict(v)
            for k, v in data.get("permanent_cache", {}).items():
                self.permanent_cache[k] = CacheEntry.from_dict(v)
            logger.info(
                f"Loaded {len(self.cache)} + {len(self.permanent_cache)} permanent entries from disk"
            )
        except Exception as exc:
            logger.warning(f"Cache load failed: {exc}")

    def _save_to_disk(self) -> None:
        try:
            data = {
                "cache": {k: v.to_dict() for k, v in self.cache.items()},
                "permanent_cache": {k: v.to_dict() for k, v in self.permanent_cache.items()},
            }
            with open(self.cache_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            logger.warning(f"Cache save failed: {exc}")

    # ------------------------------------------------------------------
    def get(self, key: str) -> Optional[CacheEntry]:
        if key in self.permanent_cache:
            entry = self.permanent_cache[key]
            entry.cache_hits += 1
            return entry
        if key in self.cache:
            entry = self.cache[key]
            entry.cache_hits += 1
            return entry
        return None

    def set(self, key: str, entry: CacheEntry) -> None:
        self.cache[key] = entry
        self._save_to_disk()

    def set_permanent(self, key: str, entry: CacheEntry) -> None:
        self.permanent_cache[key] = entry
        self._save_to_disk()

    def delete(self, key: str) -> None:
        self.cache.pop(key, None)
        self.permanent_cache.pop(key, None)
        self._save_to_disk()

    def clear(self) -> None:
        self.cache.clear()
        self.permanent_cache.clear()
        self._save_to_disk()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": "local_memory",
            "size": len(self.cache),
            "permanent_size": len(self.permanent_cache),
            "total_hits": sum(e.cache_hits for e in self.cache.values()),
            "permanent_hits": sum(e.cache_hits for e in self.permanent_cache.values()),
        }


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

class RedisCache:
    """Redis-backed cache. Requires: pip install redis"""

    def __init__(self, cache_ttl: int = 3_600_000, redis_url: Optional[str] = None):
        if not _REDIS_AVAILABLE:
            raise ImportError("redis not installed. Run: pip install redis")

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD") or None

        self.client = _redis_lib.Redis(
            host=host, port=port, password=password, decode_responses=True
        )
        self.client.ping()
        self.permanent_ttl = 315_360_000  # ~10 years
        logger.info(f"RedisCache connected: {host}:{port}")

    def get(self, key: str) -> Optional[CacheEntry]:
        try:
            raw = self.client.get(key)
            if raw:
                entry = CacheEntry.from_dict(json.loads(raw))
                entry.cache_hits += 1
                return entry
        except Exception as exc:
            logger.warning(f"Redis get: {exc}")
        return None

    def set(self, key: str, entry: CacheEntry) -> None:
        try:
            self.client.set(key, json.dumps(entry.to_dict()))
        except Exception as exc:
            logger.warning(f"Redis set: {exc}")

    def set_permanent(self, key: str, entry: CacheEntry) -> None:
        self.set(key, entry)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception as exc:
            logger.warning(f"Redis delete: {exc}")

    def clear(self) -> None:
        try:
            self.client.flushdb()
        except Exception as exc:
            logger.error(f"Redis clear: {exc}")

    def get_stats(self) -> Dict[str, Any]:
        try:
            info = self.client.info()
            return {
                "type": "redis",
                "used_memory_human": info.get("used_memory_human"),
                "db_keys": self.client.dbsize(),
                "status": "connected",
            }
        except Exception:
            return {"type": "redis", "status": "error"}

    # Semantic persistence helpers
    def save_embedding(self, key: str, vector: Any) -> None:
        try:
            vec_list = vector.tolist() if hasattr(vector, "tolist") else vector
            self.client.hset("semantic_embeddings_hash", key, json.dumps(vec_list))
        except Exception as exc:
            logger.warning(f"Redis save_embedding: {exc}")

    def get_all_embeddings(self) -> list:
        results = []
        try:
            import numpy as np
            for k, v in self.client.hgetall("semantic_embeddings_hash").items():
                results.append((np.array(json.loads(v)), k))
        except Exception as exc:
            logger.warning(f"Redis get_all_embeddings: {exc}")
        return results


# ---------------------------------------------------------------------------
# Momento
# ---------------------------------------------------------------------------

class MomentoCache:
    """Momento serverless cache. Requires: pip install momento"""

    def __init__(self, cache_name: str = "llm-service-cache", cache_ttl: int = 3_600_000):
        if not _MOMENTO_AVAILABLE:
            raise ImportError("momento not installed. Run: pip install momento")

        self.cache_name = cache_name
        self.cache_ttl = timedelta(seconds=cache_ttl / 1000)
        self.permanent_ttl = timedelta(days=36_500)

        api_key = os.getenv("MOMENTO_API_KEY")
        if not api_key:
            raise ValueError("MOMENTO_API_KEY environment variable not set")

        self.client = CacheClient(
            configuration=Configurations.Laptop.v1(),
            credential_provider=CredentialProvider.from_environment_variable("MOMENTO_API_KEY"),
            default_ttl=self.cache_ttl,
        )
        self._ensure_cache()
        logger.info(f"MomentoCache ready: {cache_name}")

    def _ensure_cache(self) -> None:
        try:
            resp = self.client.create_cache(self.cache_name)
            match resp:
                case CreateCache.Success():
                    logger.info(f"Created Momento cache '{self.cache_name}'")
                case CreateCache.AlreadyExists():
                    pass
        except Exception as exc:
            logger.warning(f"Momento cache check: {exc}")

    def get(self, key: str) -> Optional[CacheEntry]:
        try:
            resp = self.client.get(self.cache_name, key)
            match resp:
                case CacheGet.Hit() as hit:
                    entry = CacheEntry.from_dict(json.loads(hit.value_string))
                    entry.cache_hits += 1
                    return entry
                case CacheGet.Miss():
                    return None
        except Exception as exc:
            logger.warning(f"Momento get: {exc}")
        return None

    def set(self, key: str, entry: CacheEntry) -> None:
        try:
            self.client.set(self.cache_name, key, json.dumps(entry.to_dict()), self.permanent_ttl)
        except Exception as exc:
            logger.warning(f"Momento set: {exc}")

    def set_permanent(self, key: str, entry: CacheEntry) -> None:
        self.set(key, entry)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(self.cache_name, key)
        except Exception as exc:
            logger.warning(f"Momento delete: {exc}")

    def clear(self) -> None:
        logger.warning("Momento clear() not implemented (shared cache)")

    def get_stats(self) -> Dict[str, Any]:
        return {"type": "momento", "cache_name": self.cache_name, "status": "connected"}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_cache(backend: str = "local", cache_ttl: int = 3_600_000):
    """
    Instantiate the requested cache backend.
    Falls back to LocalMemoryCache on any error.
    """
    try:
        if backend == "redis":
            return RedisCache(cache_ttl=cache_ttl)
        if backend == "momento":
            return MomentoCache(cache_ttl=cache_ttl)
    except Exception as exc:
        logger.warning(f"Cache backend '{backend}' failed ({exc}), falling back to local")
    return LocalMemoryCache(cache_ttl=cache_ttl)
