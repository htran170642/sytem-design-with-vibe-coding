"""
Retry storm test.

Scenario:
  - Stock = 10 (small — exhausts almost immediately)
  - 200 concurrent users each retry up to 10 times on sold_out/error,
    using a NEW idempotency key on every retry (worst-case amplification)
  - Expected behaviour:
      * Exactly 10 users succeed (no oversell)
      * Remaining ~190+ users are handled gracefully (sold_out or rate-limited)
      * API stays responsive throughout — no crashes, no 5xx errors
      * Per-user rate limiter absorbs the retry amplification

Usage (API must be running):
    python3 infrastructure/scripts/test_retry_storm.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid

import httpx

API_URL = "http://localhost:8000"
PRODUCT_ID = "PROD-STORM-TEST"
STOCK = 10
NUM_USERS = 200
MAX_RETRIES_PER_USER = 10

# ------------------------------------------------------------------ #


async def preload_stock() -> None:
    """Reset stock via Redis directly."""
    sys.path.insert(0, ".")
    import redis.asyncio as aioredis

    from shared.config import settings

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await r.set(f"stock:{PRODUCT_ID}", STOCK)
    await r.set(f"stock_initial:{PRODUCT_ID}", STOCK)
    await r.aclose()
    print(f"[setup] stock:{PRODUCT_ID} = {STOCK}")


async def buy_with_retries(
    client: httpx.AsyncClient,
    user_id: str,
    results: dict[str, int],
    lock: asyncio.Lock,
) -> None:
    """
    One user that retries aggressively on sold_out.
    Uses a fresh idempotency key each attempt — worst case for the server.
    """
    for attempt in range(MAX_RETRIES_PER_USER):
        idempotency_key = uuid.uuid4().hex  # new key every retry

        try:
            resp = await client.post(
                f"{API_URL}/buy",
                json={
                    "user_id": user_id,
                    "product_id": PRODUCT_ID,
                    "idempotency_key": idempotency_key,
                },
                timeout=5.0,
            )
        except httpx.TimeoutException:
            async with lock:
                results["timeout"] = results.get("timeout", 0) + 1
            break

        if resp.status_code == 429:
            async with lock:
                results["rate_limited"] = results.get("rate_limited", 0) + 1
            break  # rate limited — back off, don't keep retrying

        if resp.status_code != 200:
            async with lock:
                results["error_5xx"] = results.get("error_5xx", 0) + 1
            break

        body = resp.json()
        status = body.get("status", "")

        if status == "accepted":
            async with lock:
                results["accepted"] = results.get("accepted", 0) + 1
            return  # success — stop retrying

        elif status == "sold_out":
            async with lock:
                results["sold_out_hit"] = results.get("sold_out_hit", 0) + 1
            # Retry immediately with new key — this IS the storm
            continue

    else:
        # Exhausted all retries without success
        async with lock:
            results["gave_up"] = results.get("gave_up", 0) + 1


# ------------------------------------------------------------------ #


async def run() -> None:
    await preload_stock()

    results: dict[str, int] = {}
    lock = asyncio.Lock()

    print(f"[test] Launching {NUM_USERS} users, up to {MAX_RETRIES_PER_USER} retries each")
    print(f"[test] Total possible requests: {NUM_USERS * MAX_RETRIES_PER_USER:,}")

    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        tasks = [
            buy_with_retries(client, f"storm-user-{i}", results, lock) for i in range(NUM_USERS)
        ]
        await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    # Verify stock
    import redis.asyncio as aioredis

    from shared.config import settings

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    stock_remaining = int(await r.get(f"stock:{PRODUCT_ID}") or 0)
    await r.aclose()

    print(f"\n=== Retry Storm Results ({elapsed:.1f}s) ===")
    for outcome, count in sorted(results.items()):
        print(f"  {outcome:20s}: {count:>6,}")
    print(f"  {'---':20s}")
    total = sum(results.values())
    print(f"  {'total outcomes':20s}: {total:>6,}")
    print(f"\n  Stock initial  : {STOCK}")
    print(f"  Stock remaining: {stock_remaining}")
    print(f"  Units sold     : {STOCK - stock_remaining}")
    print("=" * 40)

    # Assertions
    units_sold = STOCK - stock_remaining
    assert units_sold == STOCK, f"OVERSELL: sold {units_sold} but stock was {STOCK}"
    print(f"\n[PASS] No oversell — exactly {units_sold} units sold")

    assert (
        results.get("error_5xx", 0) == 0
    ), f"FAIL: API returned {results['error_5xx']} 5xx errors during retry storm"
    print("[PASS] Zero 5xx errors — API stayed healthy under retry storm")

    accepted = results.get("accepted", 0)
    assert accepted == STOCK, f"FAIL: expected {STOCK} accepted orders, got {accepted}"
    print(f"[PASS] Exactly {accepted} orders accepted (matches stock)")


if __name__ == "__main__":
    asyncio.run(run())
