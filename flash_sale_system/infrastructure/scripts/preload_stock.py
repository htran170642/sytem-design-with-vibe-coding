"""
Preload stock into Redis before a flash sale.

Usage:
    python infrastructure/scripts/preload_stock.py --product-id PROD001 --stock 1000
    python infrastructure/scripts/preload_stock.py --product-id PROD001 --stock 1000 --force

Options:
    --product-id    Product identifier
    --stock         Number of units available
    --force         Overwrite existing stock (default: refuse if key exists)
"""

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


async def preload(product_id: str, stock: int, force: bool) -> None:
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    key = _stock_key(product_id)
    initial_key = _initial_key(product_id)

    try:
        existing = await r.get(key)
        if existing is not None and not force:
            print(
                f"[SKIP] Key '{key}' already exists with stock={existing}. "
                "Use --force to overwrite."
            )
            return

        # Store both the live counter and the immutable initial value
        await r.set(key, stock)
        await r.set(initial_key, stock)
        print(f"[OK]   Set {key} = {stock}")
        print(f"[OK]   Set {initial_key} = {stock}")
    finally:
        await r.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preload product stock into Redis")
    parser.add_argument("--product-id", required=True, help="Product identifier")
    parser.add_argument("--stock", required=True, type=int, help="Initial stock count")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing stock key if present",
    )
    args = parser.parse_args()

    if args.stock < 0:
        print("ERROR: stock must be >= 0")
        sys.exit(1)

    asyncio.run(preload(args.product_id, args.stock, args.force))


if __name__ == "__main__":
    main()
