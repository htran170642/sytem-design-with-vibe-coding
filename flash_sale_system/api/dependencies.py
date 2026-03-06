from typing import Annotated

import structlog
from fastapi import Depends
from redis.asyncio import ConnectionPool, Redis

from shared.config import settings

logger = structlog.get_logger(__name__)

_pool: ConnectionPool | None = None


async def init_redis() -> None:
    global _pool
    _pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=50,
        decode_responses=True,
    )
    logger.info("redis_pool_initialized", url=settings.redis_url)


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()  # type: ignore[attr-defined]
        _pool = None
        logger.info("redis_pool_closed")


async def get_redis() -> Redis:  # type: ignore[type-arg]
    if _pool is None:
        raise RuntimeError("Redis pool not initialized")
    return Redis(connection_pool=_pool)


RedisDep = Annotated[Redis, Depends(get_redis)]  # type: ignore[type-arg]
