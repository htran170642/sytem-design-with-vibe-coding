"""
Integration tests for the decrement_stock Lua script — real Redis required.

These tests verify the Lua atomicity guarantees that cannot be tested
with a mocked Redis client:
  - Returns 1  when stock > 0 and decrements
  - Returns 0  when stock == 0 (sold out)
  - Returns -1 when key does not exist
  - Stock never goes below zero under concurrent pressure
  - EVALSHA works (LuaScripts.load + LuaScripts.decrement_stock)

Run: pytest tests/integration/test_lua_script.py -v
"""

import asyncio

import pytest
import redis.asyncio as aioredis

from shared.lua_scripts import LuaScripts

# ---------------------------------------------------------------------------
# Fixture: real Redis + preloaded Lua script
# ---------------------------------------------------------------------------


@pytest.fixture
async def lua(real_redis: aioredis.Redis) -> LuaScripts:
    """Return a LuaScripts instance with script pre-loaded into Redis."""
    scripts = LuaScripts()
    await scripts.load(real_redis)
    return scripts


STOCK_KEY = "stock:test-product"


# ===========================================================================
# Return value semantics
# ===========================================================================


async def test_returns_1_and_decrements_when_stock_positive(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """Stock=5 → returns 1, stock becomes 4."""
    await real_redis.set(STOCK_KEY, 5)

    result = await lua.decrement_stock(real_redis, STOCK_KEY)

    assert result == 1
    remaining = int(await real_redis.get(STOCK_KEY) or 0)
    assert remaining == 4


async def test_returns_0_when_stock_is_zero(real_redis: aioredis.Redis, lua: LuaScripts) -> None:
    """Stock=0 → sold out, returns 0, stock stays at 0."""
    await real_redis.set(STOCK_KEY, 0)

    result = await lua.decrement_stock(real_redis, STOCK_KEY)

    assert result == 0
    remaining = int(await real_redis.get(STOCK_KEY) or 0)
    assert remaining == 0  # not decremented below zero


async def test_returns_negative_1_when_key_missing(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """Key does not exist → returns -1 (product not initialised)."""
    result = await lua.decrement_stock(real_redis, "stock:nonexistent-product")
    assert result == -1


async def test_stock_1_becomes_0_returns_1(real_redis: aioredis.Redis, lua: LuaScripts) -> None:
    """Boundary: last item. Should succeed (returns 1) and leave stock at 0."""
    await real_redis.set(STOCK_KEY, 1)

    result = await lua.decrement_stock(real_redis, STOCK_KEY)

    assert result == 1
    remaining = int(await real_redis.get(STOCK_KEY) or 0)
    assert remaining == 0


async def test_stock_does_not_go_negative_on_sequential_calls(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """After stock reaches 0, subsequent calls return 0 and never go negative."""
    await real_redis.set(STOCK_KEY, 2)

    results = []
    for _ in range(5):
        r = await lua.decrement_stock(real_redis, STOCK_KEY)
        results.append(r)

    # First 2 succeed, next 3 return sold-out
    assert results[:2] == [1, 1]
    assert all(r == 0 for r in results[2:])

    final_stock = int(await real_redis.get(STOCK_KEY) or 0)
    assert final_stock == 0


# ===========================================================================
# Concurrent atomicity — the critical guarantee
# ===========================================================================


async def test_no_oversell_under_concurrent_decrement(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """
    20 concurrent callers, only 5 units in stock.
    Exactly 5 must succeed (return 1), exactly 15 must get sold-out (return 0).
    Stock must be exactly 0 after all calls.

    This is the test that proves the Lua script's atomicity guarantee.
    Without Lua, a GET + DECR sequence could oversell.
    """
    await real_redis.set(STOCK_KEY, 5)

    tasks = [lua.decrement_stock(real_redis, STOCK_KEY) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    success_count = results.count(1)
    sold_out_count = results.count(0)

    assert success_count == 5
    assert sold_out_count == 15

    final_stock = int(await real_redis.get(STOCK_KEY) or 0)
    assert final_stock == 0


async def test_concurrent_decrement_large_stock(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """100 buyers, 60 items — exactly 60 succeed."""
    await real_redis.set(STOCK_KEY, 60)

    tasks = [lua.decrement_stock(real_redis, STOCK_KEY) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    assert results.count(1) == 60
    assert results.count(0) == 40

    final_stock = int(await real_redis.get(STOCK_KEY) or 0)
    assert final_stock == 0


# ===========================================================================
# EVALSHA (LuaScripts wrapper)
# ===========================================================================


async def test_lua_scripts_load_sets_sha(real_redis: aioredis.Redis) -> None:
    """After load(), the SHA must be set (non-None)."""
    scripts = LuaScripts()
    assert scripts._decrement_sha is None
    await scripts.load(real_redis)
    assert scripts._decrement_sha is not None


async def test_lua_scripts_not_loaded_raises_runtime_error(
    real_redis: aioredis.Redis,
) -> None:
    """Calling decrement_stock before load() must raise RuntimeError."""
    scripts = LuaScripts()
    with pytest.raises(RuntimeError, match="not loaded"):
        await scripts.decrement_stock(real_redis, STOCK_KEY)


async def test_evalsha_produces_same_result_as_eval(
    real_redis: aioredis.Redis, lua: LuaScripts
) -> None:
    """Sanity: EVALSHA result matches the expected Lua logic."""
    await real_redis.set(STOCK_KEY, 3)

    r1 = await lua.decrement_stock(real_redis, STOCK_KEY)
    r2 = await lua.decrement_stock(real_redis, STOCK_KEY)
    r3 = await lua.decrement_stock(real_redis, STOCK_KEY)
    r4 = await lua.decrement_stock(real_redis, STOCK_KEY)  # sold out

    assert r1 == 1
    assert r2 == 1
    assert r3 == 1
    assert r4 == 0
