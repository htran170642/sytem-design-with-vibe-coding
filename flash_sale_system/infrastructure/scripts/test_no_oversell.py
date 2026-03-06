"""
Concurrency test: verify the Lua decrement script never oversells.

Spawns CONCURRENCY coroutines all racing to decrement the same stock key
that starts at STOCK_COUNT.  Asserts:
  - Exactly STOCK_COUNT coroutines succeeded (result == 1)
  - Zero coroutines got a result that would push stock below 0
  - Final Redis value is 0

Usage (from project root):
    python infrastructure/scripts/test_no_oversell.py
"""

import asyncio
import sys

import redis.asyncio as aioredis

sys.path.insert(0, ".")
from shared.config import settings
from shared.lua_scripts import LuaScripts

STOCK_COUNT = 100
CONCURRENCY = 500
TEST_PRODUCT = "test_oversell_check"
STOCK_KEY = f"{settings.stock_key_prefix}:{TEST_PRODUCT}"


async def run() -> None:
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    # Fresh registry — isolated from app singleton
    scripts = LuaScripts()
    await scripts.load(r)

    # Seed stock
    await r.set(STOCK_KEY, STOCK_COUNT)
    print(f"[SETUP]  {STOCK_KEY} = {STOCK_COUNT}")
    print(f"[SETUP]  Launching {CONCURRENCY} concurrent decrements ...")

    # Fire all decrements simultaneously
    results = await asyncio.gather(
        *[scripts.decrement_stock(r, STOCK_KEY) for _ in range(CONCURRENCY)]
    )

    successes = results.count(1)
    sold_out = results.count(0)
    missing = results.count(-1)
    final = int(await r.get(STOCK_KEY) or 0)

    print(f"\n[RESULT] successes  : {successes}  (expected {STOCK_COUNT})")
    print(f"[RESULT] sold-out   : {sold_out}  (expected {CONCURRENCY - STOCK_COUNT})")
    print(f"[RESULT] key-missing: {missing}  (expected 0)")
    print(f"[RESULT] final stock: {final}    (expected 0)")

    # Cleanup
    await r.delete(STOCK_KEY)
    await r.aclose()

    # Assertions
    assert successes == STOCK_COUNT, f"FAIL: got {successes} successes, expected {STOCK_COUNT}"
    assert missing == 0, "FAIL: key went missing mid-test"
    assert final == 0, f"FAIL: final stock is {final}, expected 0"

    print("\n[PASS]  No oversell — atomic Lua decrement is correct.")


if __name__ == "__main__":
    asyncio.run(run())
