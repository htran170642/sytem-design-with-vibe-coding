"""
Redis restart recovery test.

Proves AOF persistence survives a hard container restart:
  1. Write stock, idempotency key, and stream message to Redis
  2. Force-restart the Redis container
  3. Re-connect and verify all data is intact

Usage (from project root):
    python3 infrastructure/scripts/test_restart_recovery.py

Requires the Redis docker container to be running:
    docker compose -f infrastructure/docker-compose.redis.yml up -d
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time

import redis.asyncio as aioredis

sys.path.insert(0, ".")
from shared.config import settings
from shared.lua_scripts import LuaScripts
from shared.stream_schema import OrderEvent

CONTAINER = "flash_sale_redis_primary"
TEST_PRODUCT = "recovery_test_prod"
STOCK_KEY = f"{settings.stock_key_prefix}:{TEST_PRODUCT}"
IDEMPOTENCY_KEY = f"{settings.idempotency_key_prefix}:user99:test-recovery-key-0001"
TEST_ORDER_ID = "order-recovery-test-0001"


def _docker(cmd: str) -> str:
    result = subprocess.run(
        f"docker {cmd}",
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


async def write_test_data(r: aioredis.Redis) -> str:
    """Write stock, idempotency key, and one stream message."""
    # Stock
    await r.set(STOCK_KEY, 42)

    # Idempotency key (simulates a processed order)
    await r.set(IDEMPOTENCY_KEY, TEST_ORDER_ID, ex=settings.idempotency_ttl_seconds)

    # Stream message
    event = OrderEvent.create(
        order_id=TEST_ORDER_ID,
        user_id="user99",
        product_id=TEST_PRODUCT,
    )
    msg_id: str = await r.xadd(settings.orders_stream, event.to_dict())

    print(f"  stock key      : {STOCK_KEY} = 42")
    print(f"  idempotency key: {IDEMPOTENCY_KEY} = {TEST_ORDER_ID}")
    print(f"  stream message : {msg_id}")
    return msg_id


async def verify_test_data(r: aioredis.Redis, original_msg_id: str) -> bool:
    """Read back and assert all written data survived the restart."""
    ok = True

    stock = await r.get(STOCK_KEY)
    if stock == "42":
        print(f"  [PASS] stock = {stock}")
    else:
        print(f"  [FAIL] stock expected 42, got {stock!r}")
        ok = False

    idem = await r.get(IDEMPOTENCY_KEY)
    if idem == TEST_ORDER_ID:
        print(f"  [PASS] idempotency key = {idem}")
    else:
        print(f"  [FAIL] idempotency key expected {TEST_ORDER_ID!r}, got {idem!r}")
        ok = False

    # Check stream message is still there by reading from ID 0
    messages = await r.xrange(settings.orders_stream, min=original_msg_id, max=original_msg_id)
    if messages:
        _, fields = messages[0]
        if fields.get("order_id") == TEST_ORDER_ID:
            print(f"  [PASS] stream message order_id = {fields['order_id']}")
        else:
            print(f"  [FAIL] stream message order_id mismatch: {fields}")
            ok = False
    else:
        print(f"  [FAIL] stream message {original_msg_id} not found after restart")
        ok = False

    return ok


async def run() -> None:
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    # Ensure Lua scripts + stream are ready
    scripts = LuaScripts()
    await scripts.load(r)

    # ------------------------------------------------------------------ #
    print("\n[1] Writing test data to Redis ...")
    msg_id = await write_test_data(r)
    await r.aclose()

    # ------------------------------------------------------------------ #
    print(f"\n[2] Restarting container '{CONTAINER}' ...")
    _docker(f"restart {CONTAINER}")

    # Wait for Redis to come back up
    for attempt in range(20):
        time.sleep(0.5)
        try:
            check = aioredis.from_url(settings.redis_url, decode_responses=True)
            await check.ping()
            await check.aclose()
            print(f"    Redis back up after {(attempt + 1) * 0.5:.1f}s")
            break
        except Exception:
            pass
    else:
        print("    [ERROR] Redis did not come back within 10s")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    print("\n[3] Verifying data after restart ...")
    r2: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    ok = await verify_test_data(r2, msg_id)

    # Cleanup test keys
    await r2.delete(STOCK_KEY, IDEMPOTENCY_KEY)
    await r2.aclose()

    # ------------------------------------------------------------------ #
    print()
    if ok:
        print("[PASS] AOF recovery works — all data survived restart.")
    else:
        print("[FAIL] Data was lost after restart — check AOF config.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
