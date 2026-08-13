from __future__ import annotations

import abc
import os
import time
from typing import Final

SEARCH_TTL: Final[int] = 3600
RADAR_TTL: Final[int] = 300
OUTCOME_TTL: Final[int] = 3600


class CacheBackend(abc.ABC):
    @abc.abstractmethod
    async def get(self, key: str) -> bytes | None: ...
    @abc.abstractmethod
    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...
    @abc.abstractmethod
    async def delete(self, key: str) -> None: ...
    @abc.abstractmethod
    async def incr(self, key: str, ttl_seconds: int) -> int: ...
    @abc.abstractmethod
    async def count(self, key: str) -> int:
        """Sayacı artırmadan okur; yoksa 0."""


class InMemoryCache(CacheBackend):
    """Tek süreçlik geliştirme önbelleği.

    Sayaçlar da **süreli**dir: süresiz bir sayaç hız limitini kalıcı kilide,
    oturum sayacını da hiç sıfırlanmayan bir Bonferroni cezasına çevirir.
    """

    def __init__(self) -> None:
        self._data: dict[str, tuple[bytes, float]] = {}
        self._counters: dict[str, tuple[int, float]] = {}

    async def get(self, key: str) -> bytes | None:
        if key in self._data:
            val, expire = self._data[key]
            if time.time() > expire:
                del self._data[key]
                return None
            return val
        return None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self._data[key] = (value, time.time() + ttl_seconds)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._counters.pop(key, None)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        now = time.time()
        count, expire = self._counters.get(key, (0, 0.0))
        if now > expire:
            count, expire = 0, now + ttl_seconds
        count += 1
        self._counters[key] = (count, expire)
        return count

    async def count(self, key: str) -> int:
        count, expire = self._counters.get(key, (0, 0.0))
        return count if time.time() <= expire else 0


class RedisCache(CacheBackend):
    def __init__(self) -> None:
        import redis.asyncio as redis
        self._redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost"))

    async def get(self, key: str) -> bytes | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        count = int(await self._redis.incr(key))
        if count == 1:  # yalnızca ilk artışta pencere başlatılır
            await self._redis.expire(key, ttl_seconds)
        return count

    async def count(self, key: str) -> int:
        raw = await self._redis.get(key)
        return int(raw) if raw is not None else 0


_cache_instance: CacheBackend | None = None

def get_cache() -> CacheBackend:
    global _cache_instance
    if _cache_instance is None:
        backend = os.environ.get("CACHE_BACKEND", "memory")
        if backend.lower() == "redis":
            _cache_instance = RedisCache()
        else:
            _cache_instance = InMemoryCache()
    return _cache_instance
