"""
PostgreSQL insert throughput benchmark.

Measures how many order rows/second the DB can handle under concurrent load.

Runs three scenarios:
  1. Sequential inserts (baseline)
  2. Concurrent inserts — pool=10, 500 tasks
  3. Concurrent inserts — pool=10, 1000 tasks

Usage (from project root):
    python3 infrastructure/scripts/benchmark_insert.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid

import asyncpg

sys.path.insert(0, ".")
from shared.config import settings

# ------------------------------------------------------------------ #

_INSERT_SQL = """
    INSERT INTO orders (order_id, user_id, product_id, status, created_at)
    VALUES ($1, $2, $3, 'fulfilled', NOW())
    ON CONFLICT (user_id, product_id) DO NOTHING
"""

_CLEANUP_SQL = "DELETE FROM orders WHERE product_id LIKE 'BENCH-%'"


# ------------------------------------------------------------------ #


async def run_sequential(pool: asyncpg.Pool, n: int) -> float:
    """Insert n rows one at a time. Returns rows/second."""
    async with pool.acquire() as conn:
        start = time.perf_counter()
        for i in range(n):
            await conn.execute(
                _INSERT_SQL,
                uuid.uuid4(),
                f"user-seq-{i}",
                "BENCH-SEQ",
            )
        elapsed = time.perf_counter() - start
    return n / elapsed


async def _insert_one(pool: asyncpg.Pool, user_id: str, product_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(_INSERT_SQL, uuid.uuid4(), user_id, product_id)


async def run_concurrent(pool: asyncpg.Pool, n: int, label: str) -> float:
    """Insert n rows concurrently via asyncio.gather. Returns rows/second."""
    tasks = [_insert_one(pool, f"user-{label}-{i}", f"BENCH-{label}") for i in range(n)]
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    return n / elapsed


# ------------------------------------------------------------------ #


async def main() -> None:
    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
    )

    print("PostgreSQL Insert Throughput Benchmark")
    print("=" * 40)

    # Clean up any previous benchmark rows
    async with pool.acquire() as conn:
        await conn.execute(_CLEANUP_SQL)

    # 1. Sequential baseline (100 rows)
    rps = await run_sequential(pool, 100)
    print(f"Sequential  (100 rows):   {rps:,.0f} rows/sec")

    async with pool.acquire() as conn:
        await conn.execute(_CLEANUP_SQL)

    # 2. Concurrent 500 tasks
    rps = await run_concurrent(pool, 500, "C500")
    print(f"Concurrent  (500 tasks):  {rps:,.0f} rows/sec")

    async with pool.acquire() as conn:
        await conn.execute(_CLEANUP_SQL)

    # 3. Concurrent 1000 tasks
    rps = await run_concurrent(pool, 1000, "C1000")
    print(f"Concurrent (1000 tasks): {rps:,.0f} rows/sec")

    # Final cleanup
    async with pool.acquire() as conn:
        await conn.execute(_CLEANUP_SQL)

    await pool.close()
    print("=" * 40)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
