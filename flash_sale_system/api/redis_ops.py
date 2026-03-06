"""
Atomic Redis operations for the flash-sale hot path.

All stock decrements use a Lua script so the read-check-decrement
sequence is a single atomic operation — no race conditions.
Scripts are registered once at startup (EVALSHA) for efficiency.
"""

from __future__ import annotations

from redis.asyncio import Redis

from shared.config import settings
from shared.lua_scripts import lua_scripts
from shared.stream_schema import OrderEvent


def _stock_key(product_id: str) -> str:
    return f"{settings.stock_key_prefix}:{product_id}"


def _idempotency_key(user_id: str, key: str) -> str:
    # Scoped to user — prevents cross-user replay/enumeration attacks
    return f"{settings.idempotency_key_prefix}:{user_id}:{key}"


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------


async def decrement_stock(redis: Redis, product_id: str) -> bool:  # type: ignore[type-arg]
    """
    Atomically decrement stock for *product_id* via EVALSHA.
    Returns True if a unit was reserved, False if sold out or key missing.
    """
    result = await lua_scripts.decrement_stock(redis, _stock_key(product_id))
    return result == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

_PENDING = "pending"


async def claim_idempotency(redis: Redis, user_id: str, key: str) -> bool:  # type: ignore[type-arg]
    """
    Atomically claim an idempotency key via SET NX EX.

    Key is scoped to user_id — attacker cannot pre-claim another user's key.
    Returns True  → key was free; this request now owns it (marked "pending").
    Returns False → key already exists; this is a duplicate request.
    """
    result = await redis.set(
        _idempotency_key(user_id, key),
        _PENDING,
        nx=True,
        ex=settings.idempotency_ttl_seconds,
    )
    return result is not None


async def resolve_idempotency(redis: Redis, user_id: str, key: str, order_id: str) -> None:  # type: ignore[type-arg]
    """Overwrite 'pending' with the final order_id after successful processing."""
    await redis.set(
        _idempotency_key(user_id, key),
        order_id,
        ex=settings.idempotency_ttl_seconds,
    )


async def release_idempotency(redis: Redis, user_id: str, key: str) -> None:  # type: ignore[type-arg]
    """Delete a claimed-but-failed key so the caller can retry."""
    await redis.delete(_idempotency_key(user_id, key))


async def get_idempotency(redis: Redis, user_id: str, key: str) -> str | None:  # type: ignore[type-arg]
    """Return the stored value for an idempotency key (order_id or 'pending')."""
    value: str | None = await redis.get(_idempotency_key(user_id, key))
    return value


# ---------------------------------------------------------------------------
# Redis Streams
# ---------------------------------------------------------------------------


async def setup_stream(redis: Redis) -> None:  # type: ignore[type-arg]
    """
    Create the orders stream and consumer group if they don't exist.

    Uses XGROUP CREATE with MKSTREAM so the stream itself is also created
    atomically. '$' means new consumers only see messages added after joining;
    '0' would replay all existing messages — we want '$' at startup so a fresh
    deploy doesn't re-process old events that were already handled.

    Safe to call multiple times — the ResponseError for existing group is swallowed.
    """
    try:
        await redis.xgroup_create(
            settings.orders_stream,
            settings.orders_consumer_group,
            id="$",
            mkstream=True,
        )
    except Exception as exc:
        # BUSYGROUP: group already exists — expected on restart, safe to ignore
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue_order(
    redis: Redis,  # type: ignore[type-arg]
    *,
    order_id: str,
    user_id: str,
    product_id: str,
) -> None:
    """Push an OrderEvent onto the Redis Stream using the shared schema."""
    event = OrderEvent.create(
        order_id=order_id,
        user_id=user_id,
        product_id=product_id,
    )
    await redis.xadd(
        settings.orders_stream,
        event.to_dict(),
        maxlen=settings.stream_max_len,
        approximate=True,  # MAXLEN ~ — O(1) amortised, avoids blocking Redis
    )
