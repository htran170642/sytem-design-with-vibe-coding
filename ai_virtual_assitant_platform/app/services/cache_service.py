"""
Cache Service
Redis-backed async cache layer for AIVA.
Phase 6: Caching & Performance Optimization — Step 1 (Cache Foundation)
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Global key prefix for all AIVA cache entries
_KEY_PREFIX = "aiva"


@dataclass
class CacheStats:
    hits: int
    misses: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"hit_rate={self.hit_rate:.1%})"
        )


class CacheService:
    """
    Async Redis cache with JSON serialization, TTL support, and hit/miss tracking.

    Usage:
        cache = get_cache_service()
        key = CacheService.hash_key("embedding", text)
        value = await cache.get(key)
        if value is None:
            value = await compute_embedding(text)
            await cache.set(key, value, ttl=settings.CACHE_EMBEDDING_TTL)
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a cached value by key.

        Returns None (and increments miss counter) when:
        - caching is disabled globally
        - the key does not exist
        - the stored value cannot be deserialized

        Increments hit counter on a successful read.
        """
        if not settings.CACHE_ENABLED:
            return None

        t0 = time.monotonic()
        try:
            raw = await self._redis.get(key)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        except Exception as exc:
            logger.warning("Cache GET failed", extra={"key": key, "error": str(exc)})
            self._misses += 1
            return None

        if raw is None:
            self._misses += 1
            logger.debug("Cache miss", extra={"key": key, "elapsed_ms": elapsed_ms})
            return None

        try:
            value = json.loads(raw)
            self._hits += 1
            logger.debug("Cache hit", extra={"key": key, "elapsed_ms": elapsed_ms})
            return value
        except json.JSONDecodeError as exc:
            logger.warning(
                "Cache value is not valid JSON — treating as miss",
                extra={"key": key, "error": str(exc)},
            )
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.

        Args:
            key:   Cache key (use make_key or hash_key to build it).
            value: JSON-serializable value to store.
            ttl:   Time-to-live in seconds. Falls back to CACHE_DEFAULT_TTL
                   when None. Pass 0 to store without expiry (use sparingly).
        """
        if not settings.CACHE_ENABLED:
            return

        effective_ttl = ttl if ttl is not None else settings.CACHE_DEFAULT_TTL

        try:
            raw = json.dumps(value)
        except (TypeError, ValueError) as exc:
            logger.error(
                "Cannot serialize cache value to JSON — skipping set",
                extra={"key": key, "error": str(exc)},
            )
            return

        try:
            if effective_ttl > 0:
                await self._redis.setex(key, effective_ttl, raw)
            else:
                await self._redis.set(key, raw)
            logger.debug("Cache set", extra={"key": key, "ttl": effective_ttl})
        except Exception as exc:
            logger.warning("Cache SET failed", extra={"key": key, "error": str(exc)})

    async def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        try:
            await self._redis.delete(key)
            logger.debug("Cache delete", extra={"key": key})
        except Exception as exc:
            logger.warning("Cache DELETE failed", extra={"key": key, "error": str(exc)})

    async def exists(self, key: str) -> bool:
        """Return True if a key exists in the cache."""
        try:
            result = await self._redis.exists(key)
            return bool(result)
        except Exception as exc:
            logger.warning("Cache EXISTS failed", extra={"key": key, "error": str(exc)})
            return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> CacheStats:
        """Return current hit/miss counters."""
        return CacheStats(hits=self._hits, misses=self._misses)

    def reset_stats(self) -> None:
        """Reset hit/miss counters (useful for testing or periodic reporting)."""
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Key builders
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(namespace: str, *parts: str) -> str:
        """
        Build a structured cache key.

        Example:
            CacheService.make_key("ai_response", "gpt-4o", "req-abc")
            → "aiva:ai_response:gpt-4o:req-abc"
        """
        combined = ":".join(str(p) for p in parts)
        return f"{_KEY_PREFIX}:{namespace}:{combined}"

    @staticmethod
    def hash_key(namespace: str, text: str) -> str:
        """
        Build a cache key by hashing arbitrary text (suitable for long inputs
        like full prompts or document chunks).

        Example:
            CacheService.hash_key("embedding", long_chunk_text)
            → "aiva:embedding:3f4a2b1c9e7d5f6a"
        """
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{_KEY_PREFIX}:{namespace}:{digest}"


# ------------------------------------------------------------------
# Singleton factory
# ------------------------------------------------------------------

_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Return the shared CacheService singleton (created on first call)."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        logger.info(
            "CacheService initialized",
            extra={"redis_url": settings.REDIS_URL, "enabled": settings.CACHE_ENABLED},
        )
    return _cache_service
