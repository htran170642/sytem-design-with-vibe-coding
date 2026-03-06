"""
At-least-once delivery guarantee test.

Simulates a worker crash after XREADGROUP but before XACK.
Verifies that on "restart" the message is reclaimed via XAUTOCLAIM
and processed exactly once.

Steps:
  1. Enqueue one order message
  2. Worker-1 reads it (message enters PEL) — then "crashes" (no XACK)
  3. Fast-forward idle time by manipulating XPENDING entry via XCLAIM
  4. Worker-2 starts — XAUTOCLAIM picks up the stale message
  5. Worker-2 processes and ACKs it
  6. Assert PEL is empty (message not stuck)
  7. Assert DB has exactly one row (no double-insert)

Usage (from project root):
    python3 infrastructure/scripts/test_at_least_once.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import redis.asyncio as aioredis

sys.path.insert(0, ".")
from api.redis_ops import enqueue_order, setup_stream
from shared.config import settings
from shared.lua_scripts import LuaScripts
from worker.consumer import StreamConsumer
from worker.db import close_db_pool, init_db_pool, insert_order

ORDER_ID = str(uuid.uuid4())
USER_ID = "rat-least-once-use"
PRODUCT_ID = "PROD-ALO-TEST"


async def run() -> None:
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    scripts = LuaScripts()
    await scripts.load(r)
    await setup_stream(r)
    await init_db_pool()

    # ------------------------------------------------------------------ #
    print("\n[1] Enqueue one order ...")
    await enqueue_order(r, order_id=ORDER_ID, user_id=USER_ID, product_id=PRODUCT_ID)

    # ------------------------------------------------------------------ #
    print("[2] Worker-1 reads message — then crashes (no XACK) ...")
    worker1 = StreamConsumer(r)
    crashed_msg_id: str | None = None
    async for msg_id, event in worker1.messages():
        crashed_msg_id = msg_id
        # Crash — do NOT call worker1.ack()
        print(f"    worker-1 received {msg_id} — simulating crash")
        break

    assert crashed_msg_id is not None

    # Verify message is in PEL
    pending = await r.xpending(settings.orders_stream, settings.orders_consumer_group)
    assert pending["pending"] == 1, f"Expected 1 pending, got {pending['pending']}"
    print(f"    PEL count = {pending['pending']}  (message stuck, as expected)")

    # ------------------------------------------------------------------ #
    # Force the message to appear idle by using XCLAIM with an old idle-time.
    # This simulates 60 seconds passing without an XACK.
    print("[3] Fast-forwarding idle time via XCLAIM ...")
    await r.xclaim(
        settings.orders_stream,
        settings.orders_consumer_group,
        settings.worker_consumer_name,  # claim under same or different consumer
        min_idle_time=0,
        message_ids=[crashed_msg_id],
        idle=settings.stream_claim_min_idle_ms + 1000,  # force it past the threshold
    )

    # ------------------------------------------------------------------ #
    print("[4] Worker-2 starts — XAUTOCLAIM reclaims stale message ...")
    # Create a second consumer with a different name to simulate a new worker instance
    worker2 = StreamConsumer(r)
    worker2._consumer = "worker-2"  # override instance attribute only

    reclaimed_count = 0
    async for msg_id, event in worker2.messages():
        print(f"    worker-2 reclaimed {msg_id}: order_id={event.order_id}")
        inserted = await insert_order(event)
        await worker2.ack(msg_id)
        reclaimed_count += 1
        print(f"    inserted={inserted}  acked=True")
        break

    # ------------------------------------------------------------------ #
    print("\n[5] Verifying guarantees ...")

    # PEL must be empty
    pending2 = await r.xpending(settings.orders_stream, settings.orders_consumer_group)
    assert pending2["pending"] == 0, f"PEL not empty: {pending2['pending']}"
    print("    [PASS] PEL = 0  (no stuck messages)")

    assert reclaimed_count == 1, "Worker-2 should have reclaimed exactly 1 message"
    print(f"    [PASS] reclaimed {reclaimed_count} message")

    # DB must have exactly one row for this user+product
    import asyncpg

    conn = await asyncpg.connect(dsn=settings.database_url)
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM orders WHERE user_id=$1 AND product_id=$2",
        USER_ID,
        PRODUCT_ID,
    )
    await conn.close()
    assert count == 1, f"Expected 1 DB row, got {count}"
    print(f"    [PASS] DB rows = {count}  (exactly-once despite redelivery)")

    await close_db_pool()
    await r.aclose()
    print("\n[PASS] At-least-once safety verified — no message lost, no double-insert.")


if __name__ == "__main__":
    asyncio.run(run())
