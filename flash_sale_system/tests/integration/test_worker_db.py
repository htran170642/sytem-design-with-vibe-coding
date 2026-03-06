"""
Integration tests for worker.db.insert_order — requires a real PostgreSQL instance.

These tests skip automatically if PostgreSQL is not available.
They use the pg_pool fixture which:
  - Connects to the test DB
  - Wipes the orders table before/after each test for isolation
  - Closes the pool after the test

Run: pytest tests/integration/test_worker_db.py -v
"""

import uuid
from collections.abc import Generator

import asyncpg
import pytest

import worker.db as db_module
from shared.stream_schema import OrderEvent
from worker.db import insert_order

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    user_id: str = "user-1",
    product_id: str = "prod-1",
    order_id: str | None = None,
) -> OrderEvent:
    return OrderEvent.create(
        order_id=order_id or str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id,
    )


async def _count_orders(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM orders")


async def _fetch_order(pool: asyncpg.Pool, order_id: str) -> asyncpg.Record | None:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM orders WHERE order_id = $1",
            uuid.UUID(order_id),
        )


# ---------------------------------------------------------------------------
# Override module-level pool with the test pool
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def inject_test_pool(pg_pool: asyncpg.Pool) -> Generator[None, None, None]:
    """Point worker.db._pool at the test pool so insert_order uses it."""
    db_module._pool = pg_pool
    yield
    db_module._pool = None


# ===========================================================================
# insert_order — first insert
# ===========================================================================


async def test_insert_order_returns_true_on_first_insert(
    pg_pool: asyncpg.Pool,
) -> None:
    event = _make_event()
    result = await insert_order(event)
    assert result is True


async def test_insert_order_creates_row_in_db(
    pg_pool: asyncpg.Pool,
) -> None:
    event = _make_event()
    await insert_order(event)

    count = await _count_orders(pg_pool)
    assert count == 1


async def test_insert_order_stores_correct_fields(
    pg_pool: asyncpg.Pool,
) -> None:
    order_id = str(uuid.uuid4())
    event = _make_event(user_id="alice", product_id="flash-item", order_id=order_id)
    await insert_order(event)

    row = await _fetch_order(pg_pool, order_id)
    assert row is not None
    assert str(row["order_id"]) == order_id
    assert row["user_id"] == "alice"
    assert row["product_id"] == "flash-item"
    assert str(row["status"]) == "fulfilled"


async def test_insert_order_sets_fulfilled_status(
    pg_pool: asyncpg.Pool,
) -> None:
    event = _make_event()
    await insert_order(event)

    row = await _fetch_order(pg_pool, event.order_id)
    assert row is not None
    assert str(row["status"]) == "fulfilled"


async def test_insert_order_sets_created_at(
    pg_pool: asyncpg.Pool,
) -> None:
    event = _make_event()
    await insert_order(event)

    row = await _fetch_order(pg_pool, event.order_id)
    assert row is not None
    assert row["created_at"] is not None


# ===========================================================================
# insert_order — idempotent duplicate handling
# ===========================================================================


async def test_insert_order_returns_false_on_duplicate_user_product(
    pg_pool: asyncpg.Pool,
) -> None:
    """
    ON CONFLICT (user_id, product_id) DO NOTHING — second insert must return False.
    This is the core idempotency guarantee of the worker.
    """
    event1 = _make_event(user_id="user-1", product_id="prod-1")
    event2 = _make_event(
        user_id="user-1", product_id="prod-1"
    )  # different order_id, same user+product

    result1 = await insert_order(event1)
    result2 = await insert_order(event2)

    assert result1 is True
    assert result2 is False  # duplicate — not inserted again


async def test_insert_order_duplicate_does_not_create_extra_row(
    pg_pool: asyncpg.Pool,
) -> None:
    event1 = _make_event(user_id="user-1", product_id="prod-1")
    event2 = _make_event(user_id="user-1", product_id="prod-1")

    await insert_order(event1)
    await insert_order(event2)

    count = await _count_orders(pg_pool)
    assert count == 1  # exactly one row, not two


async def test_insert_order_same_order_id_is_idempotent(
    pg_pool: asyncpg.Pool,
) -> None:
    """Inserting the exact same OrderEvent twice must safely return False on second call."""
    order_id = str(uuid.uuid4())
    event = _make_event(order_id=order_id)

    r1 = await insert_order(event)
    r2 = await insert_order(event)

    assert r1 is True
    assert r2 is False

    count = await _count_orders(pg_pool)
    assert count == 1


async def test_insert_order_different_users_same_product_both_inserted(
    pg_pool: asyncpg.Pool,
) -> None:
    """Different users buying the same product are independent rows."""
    e1 = _make_event(user_id="user-A", product_id="prod-X")
    e2 = _make_event(user_id="user-B", product_id="prod-X")

    r1 = await insert_order(e1)
    r2 = await insert_order(e2)

    assert r1 is True
    assert r2 is True

    count = await _count_orders(pg_pool)
    assert count == 2


async def test_insert_order_same_user_different_products_both_inserted(
    pg_pool: asyncpg.Pool,
) -> None:
    """Same user buying different products — both rows should be inserted."""
    e1 = _make_event(user_id="user-1", product_id="prod-A")
    e2 = _make_event(user_id="user-1", product_id="prod-B")

    r1 = await insert_order(e1)
    r2 = await insert_order(e2)

    assert r1 is True
    assert r2 is True

    count = await _count_orders(pg_pool)
    assert count == 2


# ===========================================================================
# insert_order — pool not initialised
# ===========================================================================


async def test_insert_order_raises_if_pool_not_initialised() -> None:
    """Calling insert_order without calling init_db_pool() must raise RuntimeError."""
    db_module._pool = None  # simulate uninitialized state
    event = _make_event()

    with pytest.raises(RuntimeError, match="not initialized"):
        await insert_order(event)

    # Restore for other tests in the session
    # (inject_test_pool autouse fixture will reset it for the next test)


# ===========================================================================
# Multiple concurrent inserts — at-least-once safety
# ===========================================================================


async def test_concurrent_inserts_with_same_user_product_exactly_one_row(
    pg_pool: asyncpg.Pool,
) -> None:
    """
    Simulate a worker crash-redelivery scenario:
    5 concurrent insert attempts for the same (user_id, product_id).
    The UNIQUE constraint must guarantee exactly one row is committed.
    """
    import asyncio

    events = [_make_event(user_id="concurrent-user", product_id="hot-item") for _ in range(5)]

    results = await asyncio.gather(*[insert_order(e) for e in events])

    true_count = results.count(True)
    false_count = results.count(False)

    assert true_count == 1  # exactly one succeeded
    assert false_count == 4  # four were no-ops (ON CONFLICT)

    count = await _count_orders(pg_pool)
    assert count == 1
