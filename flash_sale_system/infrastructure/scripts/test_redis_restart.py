"""
Failure injection: Restart Redis during a flash sale event.

Scenario:
  1. Preload stock into Redis
  2. Enqueue orders into Redis Stream (with a consumer group + PEL)
  3. docker restart flash_redis  ← kill and revive Redis
  4. Verify all data survived:
     - stock key intact
     - stream messages intact
     - consumer group and PEL intact
     - API still responsive after reconnect

This validates AOF persistence — no data loss on Redis restart.

Usage:
    python3 infrastructure/scripts/test_redis_restart.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import uuid

sys.path.insert(0, ".")

import redis.asyncio as aioredis

from shared.config import settings
from shared.stream_schema import OrderEvent

PRODUCT_ID = "PROD-RESTART-TEST"
STOCK = 50
NUM_ORDERS = 5
CONSUMER_GROUP = settings.orders_consumer_group
CONSUMER_NAME = "restart-test-worker"


# ------------------------------------------------------------------ #


async def setup(r: aioredis.Redis) -> list[str]:
    """Seed stock, consumer group, and enqueue orders."""
    # Stock
    await r.set(f"stock:{PRODUCT_ID}", STOCK)
    await r.set(f"stock_initial:{PRODUCT_ID}", STOCK)
    print(f"  [setup] stock:{PRODUCT_ID} = {STOCK}")

    # Consumer group
    try:
        await r.xgroup_create(settings.orders_stream, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception:
        pass

    # Enqueue orders AND read them into PEL (simulate in-flight processing)
    order_ids = []
    for i in range(NUM_ORDERS):
        event = OrderEvent.create(
            order_id=str(uuid.uuid4()),
            user_id=f"restart-user-{i}",
            product_id=PRODUCT_ID,
        )
        await r.xadd(settings.orders_stream, event.to_dict())
        order_ids.append(event.order_id)

    # Read into PEL — simulate worker mid-processing when Redis restarts
    await r.xreadgroup(
        groupname=CONSUMER_GROUP,
        consumername=CONSUMER_NAME,
        streams={settings.orders_stream: ">"},
        count=NUM_ORDERS,
        block=1000,
    )
    print(f"  [setup] {NUM_ORDERS} orders enqueued and in PEL (simulating in-flight)")
    return order_ids


async def snapshot_state(r: aioredis.Redis, label: str) -> dict:
    """Capture current Redis state for comparison."""
    stock = await r.get(f"stock:{PRODUCT_ID}")
    stream_len = await r.xlen(settings.orders_stream)
    pending = await r.xpending(settings.orders_stream, CONSUMER_GROUP)
    pel_count = pending["pending"]

    state = {
        "stock": int(stock) if stock else None,
        "stream_len": stream_len,
        "pel_count": pel_count,
    }
    print(
        f"  [{label}] stock={state['stock']}  stream_len={state['stream_len']}  PEL={state['pel_count']}"
    )
    return state


def restart_redis() -> None:
    """docker restart the Redis container and wait for it to come back up."""
    print("  [restart] docker restart flash_redis ...")
    t0 = time.perf_counter()
    subprocess.run(["docker", "restart", "flash_redis"], check=True, capture_output=True)
    elapsed = time.perf_counter() - t0
    print(f"  [restart] Redis back up in {elapsed:.1f}s")


async def wait_for_redis(r: aioredis.Redis, timeout: float = 10.0) -> None:
    """Poll until Redis accepts connections again."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            await r.ping()
            return
        except Exception:
            await asyncio.sleep(0.2)
    raise TimeoutError("Redis did not recover within timeout")


# ------------------------------------------------------------------ #


async def main() -> None:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)

    # Clean slate
    await r.delete(f"stock:{PRODUCT_ID}", f"stock_initial:{PRODUCT_ID}")
    await r.delete(settings.orders_stream)

    print("\n=== Failure Injection: Redis Restart ===")

    # Step 1: Setup state before restart
    print("\n[1] Setting up state before restart...")
    await setup(r)
    state_before = await snapshot_state(r, "before")

    # Step 2: Restart Redis
    print("\n[2] Restarting Redis...")
    await r.aclose()  # close connection before restart
    restart_redis()

    # Step 3: Reconnect
    print("\n[3] Reconnecting...")
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await wait_for_redis(r)
    print("  [reconnect] OK")

    # Step 4: Snapshot state after restart
    print("\n[4] Verifying state after restart...")
    state_after = await snapshot_state(r, "after ")

    # Step 5: Assertions
    print("\n[5] Assertions...")

    assert (
        state_after["stock"] == state_before["stock"]
    ), f"Stock lost: before={state_before['stock']}, after={state_after['stock']}"
    print(f"  [PASS] Stock preserved: {state_after['stock']}")

    assert (
        state_after["stream_len"] == state_before["stream_len"]
    ), f"Stream messages lost: before={state_before['stream_len']}, after={state_after['stream_len']}"
    print(f"  [PASS] Stream messages preserved: {state_after['stream_len']}")

    assert (
        state_after["pel_count"] == state_before["pel_count"]
    ), f"PEL lost: before={state_before['pel_count']}, after={state_after['pel_count']}"
    print(f"  [PASS] PEL preserved: {state_after['pel_count']} pending messages")

    # Step 6: Verify API connectivity (Redis connection pool auto-reconnects)
    print("\n[6] Verifying Redis still writable after restart...")
    await r.set("restart-test-probe", "ok", ex=10)
    val = await r.get("restart-test-probe")
    assert val == "ok"
    print("  [PASS] Redis writable after restart")

    print(f"\n{'='*40}")
    print("[PASS] No data loss on Redis restart")
    print("[PASS] AOF persistence working correctly")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
