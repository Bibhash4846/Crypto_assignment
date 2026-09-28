import asyncio
from typing import Any, Optional
from cachetools import TTLCache
from app.core.config import settings


class InMemoryTTLCache:
    """Thread-safe, async-friendly in-memory cache with TTL expiration."""

    def __init__(self, ttl: int = settings.CACHE_TTL_SECONDS, maxsize: int = 1000):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._cache[key] = value


cache_service = InMemoryTTLCache()