"""
Failure injection: Kill worker during processing.

Scenario:
  1. Enqueue 5 orders into Redis Stream directly
  2. Start a "crash worker" that reads messages but crashes before XACK
  3. Verify messages stay in PEL (pending entry list) — not lost
  4. Start a recovery worker — it reclaims stale messages and processes them
  5. Verify all 5 orders land in PostgreSQL exactly once (no duplicates)

This validates:
  - At-least-once delivery via PEL
  - XAUTOCLAIM reclaims stale messages after idle timeout
  - ON CONFLICT DO NOTHING prevents duplicates on redelivery

Usage:
    python3 infrastructure/scripts/test_worker_crash.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid

sys.path.insert(0, ".")

import asyncpg
import redis.asyncio as aioredis

from shared.config import settings
from shared.stream_schema import OrderEvent

PRODUCT_ID = "PROD-CRASH-TEST"
NUM_ORDERS = 5
CRASH_CONSUMER = "crash-worker"
RECOVERY_CONSUMER = "recovery-worker"


# ------------------------------------------------------------------ #


async def enqueue_orders(r: aioredis.Redis) -> list[str]:
    """Push N orders directly into the stream. Returns list of order_ids."""
    order_ids = []
    for i in range(NUM_ORDERS):
        event = OrderEvent.create(
            order_id=str(uuid.uuid4()),
            user_id=f"crash-user-{i}",
            product_id=PRODUCT_ID,
        )
        await r.xadd(settings.orders_stream, event.to_dict())
        order_ids.append(event.order_id)
        print(f"  [enqueue] order {i+1}/{NUM_ORDERS}: {event.order_id[:8]}...")
    return order_ids


async def crash_worker_read(r: aioredis.Redis) -> int:
    """
    Read messages into PEL but crash before XACK.
    Returns number of messages claimed.
    """
    # Ensure consumer group exists
    try:
        await r.xgroup_create(
            settings.orders_stream, settings.orders_consumer_group, id="0", mkstream=True
        )
    except Exception:
        pass  # BUSYGROUP — already exists

    messages = await r.xreadgroup(
        groupname=settings.orders_consumer_group,
        consumername=CRASH_CONSUMER,
        streams={settings.orders_stream: ">"},
        count=NUM_ORDERS,
        block=2000,
    )

    if not messages:
        return 0

    stream_messages = messages[0][1]
    print(f"  [crash-worker] Read {len(stream_messages)} messages — simulating crash (no XACK)")
    # ← crash here: process them but never XACK
    # Messages now sit in PEL under CRASH_CONSUMER
    return len(stream_messages)


async def check_pel(r: aioredis.Redis) -> int:
    """Return number of messages stuck in PEL."""
    pending = await r.xpending(settings.orders_stream, settings.orders_consumer_group)
    count = pending["pending"]
    print(f"  [PEL] {count} messages pending (stuck in crash-worker's PEL)")
    return count


async def recovery_worker_process(r: aioredis.Redis, pool: asyncpg.Pool) -> int:
    """
    Recovery worker: claim stale PEL messages and insert into DB.
    Uses XAUTOCLAIM with min-idle=0 to reclaim immediately (test mode).
    Returns number of messages processed.
    """
    from worker.db import init_db_pool, insert_order

    await init_db_pool()

    # Force idle time to 0 so we can reclaim immediately in tests
    result = await r.xautoclaim(
        name=settings.orders_stream,
        groupname=settings.orders_consumer_group,
        consumername=RECOVERY_CONSUMER,
        min_idle_time=0,  # reclaim regardless of idle time (test only)
        start_id="0-0",
        count=NUM_ORDERS,
    )

    reclaimed = result[1]  # list of (id, fields) tuples
    print(f"  [recovery-worker] Reclaimed {len(reclaimed)} messages from PEL")

    processed = 0
    for msg_id, fields in reclaimed:
        try:
            event = OrderEvent.from_dict(fields)
            inserted = await insert_order(event)
            await r.xack(settings.orders_stream, settings.orders_consumer_group, msg_id)
            status = "inserted" if inserted else "duplicate-skipped"
            print(f"    → {event.order_id[:8]}... {status}, XACK'd")
            processed += 1
        except Exception as e:
            print(f"    → ERROR: {e}")

    return processed


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

    print("\n=== Failure Injection: Worker Crash ===")

    # Step 1: Enqueue orders
    print(f"\n[1] Enqueueing {NUM_ORDERS} orders...")
    order_ids = await enqueue_orders(r)

    # Step 2: Crash worker reads but never ACKs
    print("\n[2] Crash worker reads messages (no XACK)...")
    claimed = await crash_worker_read(r)
    assert claimed == NUM_ORDERS, f"Expected {NUM_ORDERS} messages, got {claimed}"

    # Step 3: Verify messages are stuck in PEL
    print("\n[3] Checking PEL...")
    pel_count = await check_pel(r)
    assert pel_count == NUM_ORDERS, f"Expected {NUM_ORDERS} in PEL, got {pel_count}"
    print(f"  [PASS] All {NUM_ORDERS} messages stuck in PEL — not lost after crash")

    # Step 4: DB should be empty (crash worker never wrote to DB)
    db_before = await count_db_orders(pool)
    assert db_before == 0, f"Expected 0 DB rows before recovery, got {db_before}"
    print("  [PASS] DB has 0 rows — crash worker never committed")

    # Step 5: Recovery worker reclaims and processes
    print("\n[4] Recovery worker reclaiming stale messages...")
    processed = await recovery_worker_process(r, pool)
    assert processed == NUM_ORDERS

    # Step 6: Verify DB has all orders, no duplicates
    db_after = await count_db_orders(pool)
    assert db_after == NUM_ORDERS, f"Expected {NUM_ORDERS} DB rows, got {db_after}"
    print("\n[5] Verifying DB...")
    print(f"  DB orders for {PRODUCT_ID}: {db_after}")

    # Step 7: Verify PEL is cleared
    pel_after = await check_pel(r)
    assert pel_after == 0, f"Expected PEL=0 after recovery, got {pel_after}"

    print(f"\n{'='*40}")
    print(f"[PASS] No data loss — all {NUM_ORDERS} orders recovered")
    print("[PASS] PEL cleared — no stuck messages")
    print(f"[PASS] DB has exactly {db_after} rows — no duplicates")

    await r.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
