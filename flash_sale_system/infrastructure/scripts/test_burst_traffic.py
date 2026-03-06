"""
Burst traffic test.

Scenario:
  - Stock = 100
  - 1000 users all fire POST /buy at the exact same instant (no ramp-up)
  - A asyncio.Event is used as a starting gun so all coroutines are ready
    before any request is sent — maximising concurrency at t=0

Expected behaviour:
  * Exactly 100 accepted (no oversell)
  * 900 sold_out or rate-limited
  * Zero 5xx errors
  * P99 latency stays reasonable (Redis handles the burst, no DB on hot path)

Usage (API must be running):
    python3 infrastructure/scripts/test_burst_traffic.py
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid

import httpx

API_URL = "http://localhost:8000"
PRODUCT_ID = "PROD-BURST-TEST"
STOCK = 100
NUM_USERS = 1000


# ------------------------------------------------------------------ #


async def preload_stock() -> None:
    import sys

    sys.path.insert(0, ".")
    import redis.asyncio as aioredis

    from shared.config import settings

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await r.set(f"stock:{PRODUCT_ID}", STOCK)
    await r.set(f"stock_initial:{PRODUCT_ID}", STOCK)
    await r.aclose()
    print(f"[setup] stock:{PRODUCT_ID} = {STOCK}")


async def burst_buy(
    client: httpx.AsyncClient,
    user_id: str,
    gun: asyncio.Event,
    results: dict[str, list],
    lock: asyncio.Lock,
) -> None:
    """Wait at the starting gun, then fire immediately."""
    await gun.wait()  # all coroutines block here until gun.set()

    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{API_URL}/buy",
            json={
                "user_id": user_id,
                "product_id": PRODUCT_ID,
                "idempotency_key": uuid.uuid4().hex,
            },
            timeout=10.0,
        )
        latency_ms = (time.perf_counter() - t0) * 1000

        async with lock:
            if resp.status_code == 429:
                results["rate_limited"].append(latency_ms)
            elif resp.status_code == 200:
                status = resp.json().get("status", "error")
                results[status].append(latency_ms)
            else:
                results["error_5xx"].append(latency_ms)

    except httpx.TimeoutException:
        async with lock:
            results["timeout"].append(0)


# ------------------------------------------------------------------ #


async def run() -> None:
    await preload_stock()

    results: dict[str, list] = {
        "accepted": [],
        "sold_out": [],
        "rate_limited": [],
        "error_5xx": [],
        "timeout": [],
    }
    lock = asyncio.Lock()
    gun = asyncio.Event()

    print(f"[test] Preparing {NUM_USERS} users at the starting gun...")

    limits = httpx.Limits(max_connections=NUM_USERS, max_keepalive_connections=NUM_USERS)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [burst_buy(client, f"burst-user-{i}", gun, results, lock) for i in range(NUM_USERS)]

        # All tasks are created and waiting — fire at once
        t_start = time.perf_counter()
        gun.set()
        await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t_start

    # Verify stock
    import redis.asyncio as aioredis

    from shared.config import settings

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    stock_remaining = int(await r.get(f"stock:{PRODUCT_ID}") or 0)
    await r.aclose()

    # Print results
    print(f"\n=== Burst Traffic Results ({elapsed:.2f}s) ===")
    for outcome, latencies in results.items():
        if latencies:
            p50 = statistics.median(latencies)
            p99 = sorted(latencies)[int(len(latencies) * 0.99)]
            print(f"  {outcome:15s}: {len(latencies):>5} | P50={p50:>6.0f}ms  P99={p99:>6.0f}ms")

    total = sum(len(v) for v in results.values())
    rps = total / elapsed
    print(f"\n  Total requests : {total:,}")
    print(f"  Throughput     : {rps:,.0f} req/s (burst)")
    print(f"  Stock initial  : {STOCK}")
    print(f"  Stock remaining: {stock_remaining}")
    print(f"  Units sold     : {STOCK - stock_remaining}")
    print("=" * 40)

    # Assertions
    units_sold = STOCK - stock_remaining
    assert units_sold == STOCK, f"OVERSELL: sold {units_sold}, stock was {STOCK}"
    print(f"\n[PASS] No oversell — exactly {units_sold} units sold")

    accepted = len(results["accepted"])
    assert accepted == STOCK, f"FAIL: expected {STOCK} accepted, got {accepted}"
    print(f"[PASS] Exactly {accepted} orders accepted")

    errors = len(results["error_5xx"])
    assert errors == 0, f"FAIL: {errors} 5xx errors during burst"
    print("[PASS] Zero 5xx errors — API survived the burst")


if __name__ == "__main__":
    asyncio.run(run())
