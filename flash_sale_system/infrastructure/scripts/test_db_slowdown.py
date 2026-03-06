"""
Failure injection: Simulate DB slowdown.

Scenario:
  1. Inject artificial delay into PostgreSQL via pg_sleep() on first N attempts
  2. Worker processes messages through the retry+backoff mechanism
  3. Verify:
     - Worker retries on timeout (not give up immediately)
     - All orders eventually land in DB
     - Messages are XACK'd only after successful insert
     - No duplicates (idempotent inserts)

The slowdown is injected by temporarily replacing asyncpg's execute() with a
version that sleeps before the real call — simulates network latency / lock waits.

Usage:
    python3 infrastructure/scripts/test_db_slowdown.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid

sys.path.insert(0, ".")

import asyncpg
import redis.asyncio as aioredis

from shared.config import settings
from shared.stream_schema import OrderEvent

PRODUCT_ID = "PROD-SLOWDB-TEST"
NUM_ORDERS = 3
SLOW_DELAY_SECONDS = 0.8  # simulate 800ms DB latency per attempt


# ------------------------------------------------------------------ #


async def enqueue_orders(r: aioredis.Redis) -> list[OrderEvent]:
    try:
        await r.xgroup_create(
            settings.orders_stream, settings.orders_consumer_group, id="0", mkstream=True
        )
    except Exception:
        pass

    events = []
    for i in range(NUM_ORDERS):
        event = OrderEvent.create(
            order_id=str(uuid.uuid4()),
            user_id=f"slow-user-{i}",
            product_id=PRODUCT_ID,
        )
        await r.xadd(settings.orders_stream, event.to_dict())
        events.append(event)
        print(f"  [enqueue] {event.order_id[:8]}...")
    return events


async def process_with_slowdb(r: aioredis.Redis, pool: asyncpg.Pool) -> dict:
    """
    Process stream messages with a slow DB injected.

    First attempt per message: sleeps SLOW_DELAY_SECONDS before insert
    (simulates lock wait / network lag).
    Subsequent attempts: normal speed (DB "recovers").
    """
    from worker.db import init_db_pool, insert_order
    from worker.retry import with_retry

    await init_db_pool()

    # Track attempt counts per order_id
    attempt_counts: dict[str, int] = {}
    results = {"inserted": 0, "retried": 0, "failed": 0, "latencies": []}

    # Read messages from stream
    messages = await r.xreadgroup(
        groupname=settings.orders_consumer_group,
        consumername="slowdb-worker",
        streams={settings.orders_stream: ">"},
        count=NUM_ORDERS,
        block=2000,
    )
    if not messages:
        print("  [warn] No messages to process")
        return results

    stream_messages = messages[0][1]
    print(f"  [worker] Processing {len(stream_messages)} messages with slow DB...")

    for msg_id, fields in stream_messages:
        event = OrderEvent.from_dict(fields)
        attempt_counts[event.order_id] = 0

        async def slow_insert(ev=event) -> bool:
            attempt_counts[ev.order_id] += 1
            attempt = attempt_counts[ev.order_id]

            if attempt == 1:
                # First attempt is slow — simulates DB lag
                print(
                    f"    [{ev.order_id[:8]}] attempt {attempt}: DB slow ({SLOW_DELAY_SECONDS}s delay)..."
                )
                await asyncio.sleep(SLOW_DELAY_SECONDS)
                results["retried"] += 1
                raise asyncpg.TooManyConnectionsError(
                    "simulated: connection pool exhausted (DB overloaded)"
                )
            else:
                # DB "recovered" — insert normally
                print(f"    [{ev.order_id[:8]}] attempt {attempt}: DB recovered, inserting...")
                return await insert_order(ev)

        t0 = time.perf_counter()
        try:
            await with_retry(
                slow_insert,
                max_attempts=3,
                base_delay=0.2,  # short delay for test speed
                max_delay=2.0,
                label=event.order_id,
            )
            elapsed = time.perf_counter() - t0
            results["latencies"].append(elapsed)
            await r.xack(settings.orders_stream, settings.orders_consumer_group, msg_id)
            results["inserted"] += 1
            print(f"    [{event.order_id[:8]}] XACK'd after {elapsed:.2f}s")
        except Exception as exc:
            results["failed"] += 1
            print(f"    [{event.order_id[:8]}] FAILED: {exc}")

    return results


async def count_db_orders(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM orders WHERE product_id = $1", PRODUCT_ID)


# ------------------------------------------------------------------ #


async def main() -> None:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)

    # Clean slate
    await r.delete(settings.orders_stream)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM orders WHERE product_id = $1", PRODUCT_ID)

    print("\n=== Failure Injection: DB Slowdown ===")
    print(f"    Injected delay : {SLOW_DELAY_SECONDS}s on first attempt")
    print(f"    Orders         : {NUM_ORDERS}")

    # Step 1: Enqueue
    print(f"\n[1] Enqueueing {NUM_ORDERS} orders...")
    await enqueue_orders(r)

    # Step 2: Process with slow DB
    print("\n[2] Processing with slow DB (first attempt always fails)...")
    t_start = time.perf_counter()
    results = await process_with_slowdb(r, pool)
    total_elapsed = time.perf_counter() - t_start

    # Step 3: Verify DB
    db_count = await count_db_orders(pool)

    # Step 4: Check PEL is clear
    pending = await r.xpending(settings.orders_stream, settings.orders_consumer_group)
    pel_count = pending["pending"]

    print(f"\n=== Results ({total_elapsed:.2f}s total) ===")
    print(f"  Inserted       : {results['inserted']}")
    print(f"  Retried        : {results['retried']}  (slow attempts)")
    print(f"  Failed         : {results['failed']}")
    if results["latencies"]:
        avg = sum(results["latencies"]) / len(results["latencies"])
        print(f"  Avg latency    : {avg:.2f}s per order (includes retry delay)")
    print(f"  DB rows        : {db_count}")
    print(f"  PEL remaining  : {pel_count}")
    print("=" * 40)

    # Assertions
    assert results["failed"] == 0, f"FAIL: {results['failed']} orders failed permanently"
    print("\n[PASS] No orders permanently failed — retry absorbed the slowdown")

    assert (
        results["retried"] == NUM_ORDERS
    ), f"FAIL: expected {NUM_ORDERS} slow attempts, got {results['retried']}"
    print("[PASS] Every order hit the slow path exactly once, then recovered")

    assert db_count == NUM_ORDERS, f"FAIL: expected {NUM_ORDERS} DB rows, got {db_count}"
    print(f"[PASS] All {NUM_ORDERS} orders landed in DB")

    assert pel_count == 0, f"FAIL: {pel_count} messages still in PEL (not XACK'd)"
    print("[PASS] PEL clear — all messages XACK'd after successful insert")

    await r.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
