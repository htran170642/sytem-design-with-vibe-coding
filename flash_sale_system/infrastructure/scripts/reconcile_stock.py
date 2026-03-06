"""
Stock reconciliation: detect drift between Redis and the DB source of truth.

Flow:
    initial_stock  = Redis stock_initial:{product_id}      (set at preload)
    fulfilled      = DB COUNT(orders WHERE product_id=X)   (Phase 5, stubbed)
    expected_stock = initial_stock - fulfilled
    redis_stock    = Redis stock:{product_id}

    If redis_stock != expected_stock → drift detected.
    With --fix the script resets Redis to expected_stock.

Usage:
    python infrastructure/scripts/reconcile_stock.py --product-id PROD001
    python infrastructure/scripts/reconcile_stock.py --product-id PROD001 --fix
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import redis.asyncio as aioredis

sys.path.insert(0, ".")
from shared.config import settings


def _stock_key(product_id: str) -> str:
    return f"{settings.stock_key_prefix}:{product_id}"


def _initial_key(product_id: str) -> str:
    return f"{settings.stock_key_prefix}_initial:{product_id}"


# ---------------------------------------------------------------------------
# DB query — stubbed until Phase 5 wires up PostgreSQL
# ---------------------------------------------------------------------------


async def _get_fulfilled_order_count(product_id: str) -> int | None:
    """
    Return the number of fulfilled orders from PostgreSQL.
    Returns None when the DB is not yet available (Phase 5 stub).
    """
    # TODO (Phase 5): replace with real asyncpg query:
    #   SELECT COUNT(*) FROM orders
    #   WHERE product_id = $1 AND status = 'fulfilled'
    return None


# ---------------------------------------------------------------------------
# Core reconciliation
# ---------------------------------------------------------------------------


async def reconcile(product_id: str, fix: bool) -> bool:
    """
    Check Redis stock against DB truth.

    Returns True if stock is consistent (or was fixed), False on unrecoverable
    error (e.g. initial key missing).
    """
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        raw_current = await r.get(_stock_key(product_id))
        raw_initial = await r.get(_initial_key(product_id))

        if raw_initial is None:
            print(
                f"[ERROR] Initial stock key not found for '{product_id}'. "
                "Run preload_stock.py first."
            )
            return False

        if raw_current is None:
            print(
                f"[WARN]  Live stock key missing for '{product_id}' — "
                "Redis may have been flushed."
            )
            current_stock = 0
        else:
            current_stock = int(raw_current)

        initial_stock = int(raw_initial)

        # Sanity check — current stock must be in [0, initial]
        if not (0 <= current_stock <= initial_stock):
            print(
                f"[WARN]  Stock {current_stock} is outside valid range "
                f"[0, {initial_stock}] — possible corruption."
            )

        # DB truth
        fulfilled = await _get_fulfilled_order_count(product_id)

        if fulfilled is None:
            # DB not available yet — do Redis-only sanity check
            print("[INFO]  DB not available (Phase 5 pending). " "Redis-only check:")
            print(
                f"        initial={initial_stock}  current={current_stock}  "
                f"consumed={initial_stock - current_stock}"
            )
            print("[OK]    No DB discrepancy detectable yet.")
            return True

        expected_stock = initial_stock - fulfilled

        print(f"[INFO]  product={product_id}")
        print(f"        initial_stock  = {initial_stock}")
        print(f"        fulfilled (DB) = {fulfilled}")
        print(f"        expected_stock = {expected_stock}")
        print(f"        redis_stock    = {current_stock}")

        if current_stock == expected_stock:
            print("[OK]    Stock is consistent.")
            return True

        drift = current_stock - expected_stock
        direction = "over-counted" if drift > 0 else "under-counted"
        print(f"[DRIFT] Redis is {direction} by {abs(drift)} units.")

        if fix:
            if expected_stock < 0:
                print(
                    "[ERROR] Expected stock is negative — DB has more orders "
                    "than initial stock. Manual investigation required."
                )
                return False
            await r.set(_stock_key(product_id), expected_stock)
            print(f"[FIX]   Reset {_stock_key(product_id)} → {expected_stock}")
        else:
            print("[HINT]  Run with --fix to correct Redis stock.")

        return True

    finally:
        await r.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Redis stock with DB")
    parser.add_argument("--product-id", required=True)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Reset Redis stock to DB-derived expected value",
    )
    args = parser.parse_args()

    ok = asyncio.run(reconcile(args.product_id, args.fix))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
