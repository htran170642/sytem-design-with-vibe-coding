"""
Real integration tests — real Redis, real Lua scripts, real stream entries.

What is real here:
  - Redis is an actual running process (localhost:6379/15)
  - Lua scripts actually execute inside Redis (atomic guarantee is real)
  - Stream entries are actually written with XADD
  - Idempotency keys are actually stored with TTL
  - Rate limiter counters are actually incremented in Redis

What is still mocked:
  - The FastAPI lifespan (init_redis / close_redis) — we manage
    the connection ourselves via the real_redis fixture
  - No actual TCP port is opened — httpx talks to the app in-process

Run: pytest tests/integration/ -v
"""

import asyncio

import redis.asyncio as aioredis
from httpx import AsyncClient

from tests.integration.conftest import (
    get_stock,
    get_stream_entries,
    preload_stock,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRODUCT = "flash-product-1"

# idempotency_key requires min_length=16
_DEFAULT_IDEM_KEY = "idem-key-1234567890"  # 20 chars


def buy_payload(
    user_id: str = "user-1",
    product_id: str = PRODUCT,
    idempotency_key: str = _DEFAULT_IDEM_KEY,
) -> dict:
    return {
        "user_id": user_id,
        "product_id": product_id,
        "idempotency_key": idempotency_key,
    }


def _idem(suffix: str | int) -> str:
    """Build a ≥16-char idempotency key from a short suffix."""
    key = f"idem-key-{suffix}"
    # Pad to at least 16 chars
    return key.ljust(16, "0")


# ===========================================================================
# 1. Health check
# ===========================================================================


class TestHealth:
    async def test_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_redis_status_is_ok(self, client: AsyncClient) -> None:
        """Proves the real Redis is reachable from inside the route."""
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        assert data["redis"] == "ok"


# ===========================================================================
# 2. Successful purchase — verify Redis state after
# ===========================================================================


class TestBuyAccepted:
    async def test_returns_accepted_status(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        await preload_stock(real_redis, PRODUCT, 100)

        response = await client.post("/buy", json=buy_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async def test_order_id_is_present(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        await preload_stock(real_redis, PRODUCT, 100)

        response = await client.post("/buy", json=buy_payload())

        import uuid

        order_id = response.json()["order_id"]
        uuid.UUID(order_id)  # raises if not valid UUID

    async def test_stock_is_decremented_in_redis(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        The most important stock test — proves the Lua script ran in real Redis
        and actually changed the stock value.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        await client.post("/buy", json=buy_payload())

        remaining = await get_stock(real_redis, PRODUCT)
        assert remaining == 99  # exactly one unit consumed

    async def test_order_event_written_to_stream(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Proves XADD ran and the message is actually in the Redis Stream.
        This is what the worker (Phase 4) will consume.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        response = await client.post("/buy", json=buy_payload())
        order_id = response.json()["order_id"]

        entries = await get_stream_entries(real_redis)

        assert len(entries) == 1
        assert entries[0]["order_id"] == order_id
        assert entries[0]["user_id"] == "user-1"
        assert entries[0]["product_id"] == PRODUCT

    async def test_idempotency_key_written_to_redis(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Proves the idempotency key was stored with the order_id as value.
        Key is user-scoped: 'idempotency:<user_id>:<idempotency_key>'.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        response = await client.post(
            "/buy", json=buy_payload(user_id="user-1", idempotency_key=_DEFAULT_IDEM_KEY)
        )
        order_id = response.json()["order_id"]

        stored = await real_redis.get(f"idempotency:user-1:{_DEFAULT_IDEM_KEY}")
        assert stored == order_id

    async def test_idempotency_key_has_ttl(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """Idempotency key must have a TTL to prevent indefinite key leak."""
        await preload_stock(real_redis, PRODUCT, 100)
        await client.post(
            "/buy", json=buy_payload(user_id="user-1", idempotency_key=_DEFAULT_IDEM_KEY)
        )

        ttl = await real_redis.ttl(f"idempotency:user-1:{_DEFAULT_IDEM_KEY}")
        assert ttl > 0  # has expiry
        assert ttl <= 86400  # within 24h window


# ===========================================================================
# 3. Sold out
# ===========================================================================


class TestSoldOut:
    async def test_sold_out_when_stock_is_zero(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        await preload_stock(real_redis, PRODUCT, 0)

        response = await client.post("/buy", json=buy_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "sold_out"

    async def test_sold_out_does_not_write_to_stream(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        await preload_stock(real_redis, PRODUCT, 0)

        await client.post("/buy", json=buy_payload())

        entries = await get_stream_entries(real_redis)
        assert len(entries) == 0

    async def test_last_item_then_sold_out(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Preload stock=1. First buyer gets it, second gets sold_out.
        Verifies the Lua script correctly handles the boundary case.
        """
        await preload_stock(real_redis, PRODUCT, 1)

        r1 = await client.post(
            "/buy", json=buy_payload(user_id="user-1", idempotency_key=_idem("key-1-"))
        )
        r2 = await client.post(
            "/buy", json=buy_payload(user_id="user-2", idempotency_key=_idem("key-2-"))
        )

        assert r1.json()["status"] == "accepted"
        assert r2.json()["status"] == "sold_out"

        final_stock = await get_stock(real_redis, PRODUCT)
        assert final_stock == 0  # exactly 0, not negative

    async def test_stock_never_goes_negative(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        The Lua script checks stock > 0 before decrementing.
        Even if 5 requests arrive with stock=1, stock must not go below 0.
        """
        await preload_stock(real_redis, PRODUCT, 1)

        for i in range(5):
            await client.post(
                "/buy", json=buy_payload(user_id=f"user-{i}", idempotency_key=_idem(f"{i}-stock-"))
            )

        final_stock = await get_stock(real_redis, PRODUCT)
        assert final_stock == 0  # never negative


# ===========================================================================
# 4. Idempotency — duplicate requests
# ===========================================================================


class TestIdempotency:
    async def test_duplicate_returns_accepted_with_cached_order_id(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Two identical requests: first is 'accepted', second returns 'accepted'
        with the cached order_id (resolved from Redis idempotency key).
        """
        await preload_stock(real_redis, PRODUCT, 100)

        r1 = await client.post("/buy", json=buy_payload())
        r2 = await client.post("/buy", json=buy_payload())  # same payload

        assert r1.json()["status"] == "accepted"
        assert r2.json()["status"] == "accepted"
        # Second request returns the same order_id as the first
        assert r1.json()["order_id"] == r2.json()["order_id"]

    async def test_duplicate_does_not_decrement_stock_twice(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        The most important idempotency test.
        Two identical requests must consume only ONE unit of stock.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        await client.post("/buy", json=buy_payload())
        await client.post("/buy", json=buy_payload())  # duplicate

        remaining = await get_stock(real_redis, PRODUCT)
        assert remaining == 99  # only one unit consumed, not two

    async def test_duplicate_does_not_write_to_stream_twice(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """Only one stream entry must exist — the worker processes this order once."""
        await preload_stock(real_redis, PRODUCT, 100)

        await client.post("/buy", json=buy_payload())
        await client.post("/buy", json=buy_payload())  # duplicate

        entries = await get_stream_entries(real_redis)
        assert len(entries) == 1  # NOT 2

    async def test_different_idempotency_keys_are_independent(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Different idempotency keys = different requests (even same user+product).
        Both should be accepted and decrement stock.
        Note: in Phase 5, DB UNIQUE constraint catches the second at DB level.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        r1 = await client.post("/buy", json=buy_payload(idempotency_key=_idem("key-A-")))
        r2 = await client.post("/buy", json=buy_payload(idempotency_key=_idem("key-B-")))

        # Both accepted at API level (DB constraint is Phase 5)
        assert r1.json()["status"] == "accepted"
        assert r2.json()["status"] == "accepted"

        remaining = await get_stock(real_redis, PRODUCT)
        assert remaining == 98  # two units consumed


# ===========================================================================
# 5. Rate limiting — real counters in Redis
# ===========================================================================


class TestRateLimiting:
    async def test_per_user_limit_enforced(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Send 11 requests for the same user (limit=10 per second).
        The 11th must be rate-limited.
        """
        await preload_stock(real_redis, PRODUCT, 1000)

        responses = []
        for i in range(11):
            r = await client.post("/buy", json=buy_payload(idempotency_key=_idem(f"{i}-limit-")))
            responses.append(r)

        statuses = [r.status_code for r in responses]

        # First 10 pass rate limit
        assert all(s == 200 for s in statuses[:10])
        # 11th is rate-limited
        assert statuses[10] == 429
        assert "Rate limit" in responses[10].json()["detail"]

    async def test_rate_limit_counter_exists_in_redis(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        After one request, the rl:user:<user_id> key must exist in Redis
        with value 1 and a TTL of 1 second.
        """
        await preload_stock(real_redis, PRODUCT, 100)

        await client.post("/buy", json=buy_payload(user_id="user-rl-check"))

        count = await real_redis.get("rl:user:user-rl-check")
        assert count == "1"

        ttl = await real_redis.ttl("rl:user:user-rl-check")
        assert 0 < ttl <= 1  # expires within 1 second

    async def test_different_users_have_separate_counters(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """user-A making 10 requests must not affect user-B's limit."""
        await preload_stock(real_redis, PRODUCT, 1000)

        # user-A burns their 10 requests
        for i in range(10):
            await client.post(
                "/buy", json=buy_payload(user_id="user-A", idempotency_key=_idem(f"a-{i}-"))
            )

        # user-B's first request must still pass
        r = await client.post(
            "/buy", json=buy_payload(user_id="user-B", idempotency_key=_idem("b-0------"))
        )

        assert r.status_code == 200
        assert r.json()["status"] != "rate_limited"


# ===========================================================================
# 6. Concurrency — the critical flash sale scenario
# ===========================================================================


class TestConcurrency:
    async def test_no_oversell_under_concurrent_load(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        THE most important test for a flash sale system.

        10 concurrent buyers, only 5 items in stock.
        The Lua script must guarantee exactly 5 get accepted and 5 get sold_out.
        Stock must end at exactly 0, never negative.
        """
        await preload_stock(real_redis, PRODUCT, 5)

        tasks = [
            client.post(
                "/buy",
                json=buy_payload(
                    user_id=f"concurrent-user-{i}",
                    idempotency_key=_idem(f"concurrent-{i:04d}"),
                ),
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        statuses = [r.json()["status"] for r in responses]
        accepted_count = statuses.count("accepted")
        sold_out_count = statuses.count("sold_out")

        assert accepted_count == 5
        assert sold_out_count == 5

        final_stock = await get_stock(real_redis, PRODUCT)
        assert final_stock == 0

    async def test_concurrent_stream_entries_match_accepted_count(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """The number of stream entries must equal the number of accepted orders."""
        await preload_stock(real_redis, PRODUCT, 3)

        tasks = [
            client.post(
                "/buy",
                json=buy_payload(user_id=f"user-{i}", idempotency_key=_idem(f"stream-{i:04d}")),
            )
            for i in range(8)
        ]
        responses = await asyncio.gather(*tasks)

        accepted_count = sum(1 for r in responses if r.json()["status"] == "accepted")
        stream_entries = await get_stream_entries(real_redis)

        assert accepted_count == 3
        assert len(stream_entries) == 3

    async def test_concurrent_no_duplicate_order_ids(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """Every accepted order must have a unique order_id."""
        await preload_stock(real_redis, PRODUCT, 20)

        tasks = [
            client.post(
                "/buy",
                json=buy_payload(user_id=f"user-{i}", idempotency_key=_idem(f"uuid-{i:04d}")),
            )
            for i in range(20)
        ]
        responses = await asyncio.gather(*tasks)

        order_ids = [r.json()["order_id"] for r in responses if r.json()["status"] == "accepted"]

        assert len(order_ids) == len(set(order_ids))


# ===========================================================================
# 7. Redis state inspection helpers — sanity checks
# ===========================================================================


class TestRedisState:
    async def test_stream_key_is_orders(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """Verifies the stream is written to the correct key name."""
        await preload_stock(real_redis, PRODUCT, 10)
        await client.post("/buy", json=buy_payload())

        stream_exists = await real_redis.exists("orders")
        assert stream_exists == 1

    async def test_stock_key_format(self, client: AsyncClient, real_redis: aioredis.Redis) -> None:
        """Verifies the stock key name the API reads from."""
        await preload_stock(real_redis, PRODUCT, 5)

        raw = await real_redis.get(f"stock:{PRODUCT}")
        assert raw == "5"

    async def test_full_redis_state_after_successful_buy(
        self, client: AsyncClient, real_redis: aioredis.Redis
    ) -> None:
        """
        Snapshot all Redis state after one successful purchase.
        Documents exactly what is written where.
        """
        idem_key = "alice-buy-1234567890"  # 20 chars
        await preload_stock(real_redis, PRODUCT, 10)

        response = await client.post(
            "/buy",
            json=buy_payload(
                user_id="alice",
                idempotency_key=idem_key,
            ),
        )
        order_id = response.json()["order_id"]

        # 1. Stock decremented
        stock = await real_redis.get(f"stock:{PRODUCT}")
        assert stock == "9"

        # 2. Idempotency key written (user-scoped)
        idem_val = await real_redis.get(f"idempotency:alice:{idem_key}")
        assert idem_val == order_id

        # 3. Stream entry written — check required fields (entry also has timestamp/version)
        entries = await get_stream_entries(real_redis)
        assert len(entries) == 1
        assert entries[0]["order_id"] == order_id
        assert entries[0]["user_id"] == "alice"
        assert entries[0]["product_id"] == PRODUCT

        # 4. Rate limiter key written for alice
        rl_val = await real_redis.get("rl:user:alice")
        assert rl_val == "1"
