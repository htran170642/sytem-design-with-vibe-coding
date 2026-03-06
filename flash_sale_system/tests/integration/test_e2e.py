"""
End-to-end integration tests — requires BOTH real Redis AND real PostgreSQL.

Simulates the full flash sale pipeline:
  1. Client sends POST /buy  (FastAPI API layer)
  2. API checks idempotency in Redis
  3. API runs atomic Lua stock decrement in Redis
  4. API writes order event to Redis Stream
  5. Worker reads from Redis Stream (StreamConsumer)
  6. Worker inserts order into PostgreSQL (insert_order)
  7. Worker ACKs the message

This is the closest to production behaviour without running separate processes.

Run: pytest tests/integration/test_e2e.py -v
"""

import asyncio
from collections.abc import Generator

import asyncpg
import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

import worker.db as db_module
from shared.stream_schema import OrderEvent
from tests.integration.conftest import (
    get_stock,
    get_stream_entries,
    preload_stock,
)
from worker.db import insert_order

# ---------------------------------------------------------------------------
# Setup: inject test pool into worker.db
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def inject_test_pool(pg_pool: asyncpg.Pool) -> Generator[None, None, None]:
    db_module._pool = pg_pool
    yield
    db_module._pool = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRODUCT = "e2e-product"


def _buy_payload(
    user_id: str = "e2e-user-1",
    product_id: str = PRODUCT,
    idempotency_key: str = "e2e-key-1234567890",  # ≥16 chars
) -> dict:
    return {
        "user_id": user_id,
        "product_id": product_id,
        "idempotency_key": idempotency_key,
    }


def _idem(suffix: str | int) -> str:
    """Build a ≥16-char idempotency key from a short suffix."""
    key = f"e2e-key-{suffix}"
    return key.ljust(16, "0")


async def _drain_stream_to_db(real_redis: aioredis.Redis) -> list[bool]:
    """
    Create a consumer group (if not exists) and process all pending messages.
    Returns list of insert_order results (True=inserted, False=duplicate).
    """
    stream = "orders"
    group = "order-workers"

    # Create consumer group — ignore error if already exists
    try:
        await real_redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception:  # noqa: S110
        pass  # group already exists from previous test
    results: list[bool] = []

    # Read pending messages (those not yet delivered to any consumer)
    raw = await real_redis.xreadgroup(
        groupname=group,
        consumername="test-worker",
        streams={stream: ">"},
        count=100,
    )

    if not raw:
        return results

    for _stream_name, entries in raw:
        for msg_id, fields in entries:
            event = OrderEvent.from_dict(fields)
            inserted = await insert_order(event)
            results.append(inserted)
            await real_redis.xack(stream, group, msg_id)

    return results


async def _count_orders(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM orders")


async def _fetch_order_by_user_product(
    pool: asyncpg.Pool, user_id: str, product_id: str
) -> asyncpg.Record | None:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM orders WHERE user_id = $1 AND product_id = $2",
            user_id,
            product_id,
        )


# ===========================================================================
# 1. Single successful purchase — full pipeline
# ===========================================================================


class TestSinglePurchase:
    async def test_e2e_stock_decremented_and_order_in_db(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        """
        Full pipeline for one purchase:
          - Redis stock goes from 10 → 9
          - 1 stream entry exists
          - 1 DB row exists after worker processes the stream
        """
        await preload_stock(real_redis, PRODUCT, 10)

        response = await client.post("/buy", json=_buy_payload())
        assert response.json()["status"] == "accepted"
        order_id = response.json()["order_id"]

        # Verify Redis state after API call
        remaining = await get_stock(real_redis, PRODUCT)
        assert remaining == 9

        stream_entries = await get_stream_entries(real_redis)
        assert len(stream_entries) == 1

        # Simulate worker: drain stream to DB
        insert_results = await _drain_stream_to_db(real_redis)
        assert insert_results == [True]  # one new row

        # Verify DB state
        count = await _count_orders(pg_pool)
        assert count == 1

        row = await _fetch_order_by_user_product(pg_pool, "e2e-user-1", PRODUCT)
        assert row is not None
        assert str(row["order_id"]) == order_id
        assert str(row["status"]) == "fulfilled"

    async def test_e2e_idempotency_key_survives_worker_redelivery(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        """
        If the worker processes the same stream entry twice (crash scenario),
        the second insert must be a no-op (ON CONFLICT DO NOTHING).
        """
        await preload_stock(real_redis, PRODUCT, 10)

        await client.post("/buy", json=_buy_payload())
        event = OrderEvent.from_dict((await get_stream_entries(real_redis))[0])

        # Worker processes the event twice (simulated re-delivery)
        r1 = await insert_order(event)
        r2 = await insert_order(event)

        assert r1 is True  # first insert succeeds
        assert r2 is False  # second is a safe no-op

        count = await _count_orders(pg_pool)
        assert count == 1  # exactly one row


# ===========================================================================
# 2. Sold-out — stream stays empty, DB untouched
# ===========================================================================


class TestSoldOut:
    async def test_e2e_sold_out_no_stream_no_db_row(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        await preload_stock(real_redis, PRODUCT, 0)

        response = await client.post("/buy", json=_buy_payload())
        assert response.json()["status"] == "sold_out"

        stream_entries = await get_stream_entries(real_redis)
        assert len(stream_entries) == 0

        # No messages to drain → no DB rows
        count = await _count_orders(pg_pool)
        assert count == 0


# ===========================================================================
# 3. Duplicate request — idempotency across API + DB
# ===========================================================================


class TestDuplicateRequest:
    async def test_e2e_duplicate_api_request_yields_one_db_row(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        """
        Two identical API requests (same idempotency key).
        Only one order must exist in the DB.
        """
        await preload_stock(real_redis, PRODUCT, 10)

        r1 = await client.post("/buy", json=_buy_payload())
        r2 = await client.post("/buy", json=_buy_payload())  # same payload

        assert r1.json()["status"] == "accepted"
        # Second request is served from the idempotency cache → 'accepted' with same order_id
        assert r2.json()["status"] == "accepted"
        assert r2.json()["order_id"] == r1.json()["order_id"]

        # Only 1 stream entry (second request is short-circuited at API)
        stream_entries = await get_stream_entries(real_redis)
        assert len(stream_entries) == 1

        # Worker drains → 1 DB row
        await _drain_stream_to_db(real_redis)
        count = await _count_orders(pg_pool)
        assert count == 1


# ===========================================================================
# 4. Concurrent buyers — no overselling end-to-end
# ===========================================================================


class TestConcurrentBuyers:
    async def test_e2e_no_oversell_5_buyers_3_items(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        """
        5 concurrent buyers, 3 items.
        - Exactly 3 accepted, 2 sold_out (or rate-limited)
        - Exactly 3 stream entries
        - Exactly 3 DB rows after worker drains
        - Redis stock exactly 0 (never negative)
        """
        await preload_stock(real_redis, PRODUCT, 3)

        tasks = [
            client.post(
                "/buy",
                json=_buy_payload(
                    user_id=f"e2e-concurrent-{i}",
                    idempotency_key=_idem(f"concurrent-{i:04d}"),
                ),
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        accepted = [r for r in responses if r.json()["status"] == "accepted"]

        assert len(accepted) == 3

        final_stock = await get_stock(real_redis, PRODUCT)
        assert final_stock == 0

        stream_entries = await get_stream_entries(real_redis)
        assert len(stream_entries) == 3

        # Worker processes all 3
        insert_results = await _drain_stream_to_db(real_redis)
        assert insert_results.count(True) == 3

        db_count = await _count_orders(pg_pool)
        assert db_count == 3

    async def test_e2e_concurrent_no_duplicate_db_rows(
        self,
        client: AsyncClient,
        real_redis: aioredis.Redis,
        pg_pool: asyncpg.Pool,
    ) -> None:
        """
        20 buyers, 20 items — all should be accepted.
        DB must have exactly 20 unique rows.
        """
        await preload_stock(real_redis, PRODUCT, 20)

        tasks = [
            client.post(
                "/buy",
                json=_buy_payload(
                    user_id=f"e2e-user-{i}",
                    idempotency_key=_idem(f"{i:010d}"),
                ),
            )
            for i in range(20)
        ]
        responses = await asyncio.gather(*tasks)

        accepted_count = sum(1 for r in responses if r.json()["status"] == "accepted")
        assert accepted_count == 20

        # Drain stream
        insert_results = await _drain_stream_to_db(real_redis)
        assert all(r is True for r in insert_results)

        db_count = await _count_orders(pg_pool)
        assert db_count == 20
