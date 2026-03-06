"""
PostgreSQL order persistence for the flash-sale worker.

insert_order() is intentionally idempotent:
  - The orders table has a UNIQUE(user_id, product_id) constraint (Phase 5).
  - A duplicate INSERT raises UniqueViolationError, which we catch and ignore.
  - This means even if a message is redelivered (at-least-once), the DB ends up
    with exactly one row per (user_id, product_id) pair.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from shared.config import settings
from shared.metrics import DB_WRITE_LATENCY, ORDERS_PROCESSED
from shared.stream_schema import OrderEvent

logger = logging.getLogger(__name__)

# Module-level connection pool — initialised once in main()
_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Create the asyncpg connection pool. Call once at worker startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=10,
    )
    logger.info("db_pool_initialized")


async def close_db_pool() -> None:
    """Drain and close the pool. Call on graceful shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("db_pool_closed")


@asynccontextmanager
async def _connection() -> AsyncIterator[asyncpg.Connection]:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db_pool() first")
    async with _pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Core insert
# ---------------------------------------------------------------------------

_INSERT_SQL = """
    INSERT INTO orders (order_id, user_id, product_id, status, created_at)
    VALUES ($1, $2, $3, 'fulfilled', NOW())
    ON CONFLICT (user_id, product_id) DO NOTHING
"""
#
# ON CONFLICT DO NOTHING is equivalent to catching UniqueViolationError but
# avoids a round-trip exception — slightly faster and cleaner.
# The UNIQUE constraint is defined in Phase 5 migrations.


async def insert_order(event: OrderEvent) -> bool:
    """
    Persist an order to PostgreSQL.

    Returns:
        True   — row was inserted (first time)
        False  — row already existed (idempotent duplicate, safe to XACK)

    Raises:
        asyncpg.PostgresError — unexpected DB error; caller should NOT XACK.
    """
    t0 = time.perf_counter()
    async with _connection() as conn:
        result = await conn.execute(
            _INSERT_SQL,
            uuid.UUID(event.order_id),  # asyncpg UUID column requires uuid.UUID object
            event.user_id,
            event.product_id,
        )
        # execute() returns a status string like "INSERT 0 1" or "INSERT 0 0"
        inserted = result.endswith("1")
    DB_WRITE_LATENCY.observe(time.perf_counter() - t0)

    if inserted:
        ORDERS_PROCESSED.labels(result="inserted").inc()
        logger.info(
            "order_inserted",
            extra={
                "order_id": event.order_id,
                "user_id": event.user_id,
                "product_id": event.product_id,
            },
        )
    else:
        ORDERS_PROCESSED.labels(result="duplicate").inc()
        logger.info(
            "order_duplicate_skipped",
            extra={"order_id": event.order_id},
        )

    return inserted
