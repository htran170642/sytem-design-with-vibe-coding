"""
Integration test fixtures — uses a REAL Redis instance (and optionally PostgreSQL).

Requirements:
  - Redis running at localhost:6379  (or set REDIS_TEST_URL env var)
  - Tests use database index 15 to avoid touching any real data
  - PostgreSQL (optional): set PG_TEST_URL env var or use the default DSN
    DB integration tests are skipped automatically if PostgreSQL is unavailable.

Run only integration tests:
    pytest tests/integration/ -v

Run only unit tests (skip integration):
    pytest tests/ --ignore=tests/integration -v
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

import api.routes.buy as buy_module
from api.circuit_breaker import State, redis_circuit_breaker
from api.dependencies import get_redis
from api.main import app
from api.redis_ops import setup_stream
from shared.lua_scripts import lua_scripts

# Use a dedicated test database — never touches db 0
REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "redis://localhost:6379/15")

# PostgreSQL test DSN — uses the same DB as the worker but safely cleans up rows
PG_TEST_URL = os.getenv(
    "PG_TEST_URL",
    "postgresql://flash_sale:flash_sale@localhost:5432/flash_sale",
)


# ---------------------------------------------------------------------------
# Reset singletons (same as outer conftest, needed here too)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    buy_module._rate_limiter = None
    redis_circuit_breaker._failures = 0
    redis_circuit_breaker._state = State.CLOSED
    redis_circuit_breaker._opened_at = 0.0


# ---------------------------------------------------------------------------
# Real Redis connection
# ---------------------------------------------------------------------------


@pytest.fixture
async def real_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    Connect to the real Redis test database.
    Skips the test if Redis is not reachable.
    Flushes db 15 before AND after each test for a clean slate.
    """
    r: aioredis.Redis = aioredis.from_url(REDIS_TEST_URL, decode_responses=True)

    try:
        await r.ping()
    except Exception:
        await r.aclose()  # type: ignore[attr-defined]
        pytest.skip(f"Redis not available at {REDIS_TEST_URL}")

    await r.flushdb()  # clean before test
    yield r
    await r.flushdb()  # clean after test
    await r.aclose()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FastAPI client backed by real Redis
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(real_redis: aioredis.Redis) -> AsyncClient:
    """
    httpx AsyncClient that hits the real FastAPI app with a real Redis.

    - Loads Lua scripts and creates consumer group (normally done by lifespan)
    - lifespan init/close are patched out (we manage the connection ourselves)
    - get_redis dependency is overridden to return real_redis
    """
    # ASGITransport does not run the ASGI lifespan, so we must manually
    # perform the setup that the lifespan would do.
    await lua_scripts.load(real_redis)
    await setup_stream(real_redis)

    app.dependency_overrides[get_redis] = lambda: real_redis
    with (
        patch("api.main.init_redis", new_callable=AsyncMock),
        patch("api.main.close_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


async def preload_stock(redis: aioredis.Redis, product_id: str, qty: int) -> None:
    """Seed Redis with stock count — simulates Phase 3 preload step."""
    await redis.set(f"stock:{product_id}", qty)


async def get_stock(redis: aioredis.Redis, product_id: str) -> int:
    """Read current stock level from Redis."""
    val = await redis.get(f"stock:{product_id}")
    return int(val) if val is not None else 0


async def get_stream_entries(redis: aioredis.Redis) -> list[dict]:
    """Read all entries from the orders stream."""
    raw = await redis.xrange("orders")
    # raw = [("1234-0", {"order_id": "...", "user_id": "...", ...}), ...]
    return [fields for _, fields in raw]


# ---------------------------------------------------------------------------
# Real PostgreSQL connection pool
# ---------------------------------------------------------------------------


@pytest.fixture
async def pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """
    Create an asyncpg connection pool against the test PostgreSQL DB.
    Skips the test if PostgreSQL is not reachable or schema is missing.
    Deletes all rows from the orders table before AND after each test.
    """
    try:
        pool: asyncpg.Pool = await asyncpg.create_pool(
            dsn=PG_TEST_URL,
            min_size=1,
            max_size=5,
            command_timeout=5,
        )
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available at {PG_TEST_URL}: {exc}")

    # Verify the orders table exists (schema must be pre-applied)
    async with pool.acquire() as conn:
        try:
            await conn.fetchval("SELECT 1 FROM orders LIMIT 1")
        except asyncpg.UndefinedTableError:
            await pool.close()
            pytest.skip("orders table not found — run infrastructure/postgres/init.sql first")

    # Clean slate: delete test rows before test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM orders")

    yield pool

    # Clean up after test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM orders")
    await pool.close()
