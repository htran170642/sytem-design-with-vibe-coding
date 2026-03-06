"""
Unit tests for api.redis_ops — mocked Redis client.

Tests the Python-layer logic (key naming, return value interpretation,
argument passing) for every public function:
  - decrement_stock       — delegates to lua_scripts.decrement_stock (mocked)
  - claim_idempotency     — SET NX
  - resolve_idempotency   — SET (overwrite pending → order_id)
  - release_idempotency   — DELETE
  - get_idempotency       — GET
  - enqueue_order         — XADD

The Lua script itself is tested separately in tests/integration/test_lua_script.py.
"""

from unittest.mock import AsyncMock, patch

import pytest

from api.redis_ops import (
    claim_idempotency,
    decrement_stock,
    enqueue_order,
    get_idempotency,
    release_idempotency,
    resolve_idempotency,
)
from shared.config import settings


@pytest.fixture
def redis() -> AsyncMock:
    return AsyncMock()


# ===========================================================================
# decrement_stock — delegates to lua_scripts
# ===========================================================================


async def test_decrement_stock_returns_true_when_lua_returns_1(redis: AsyncMock) -> None:
    with patch("api.redis_ops.lua_scripts") as mock_lua:
        mock_lua.decrement_stock = AsyncMock(return_value=1)
        result = await decrement_stock(redis, "product-A")
    assert result is True


async def test_decrement_stock_returns_false_when_lua_returns_0(redis: AsyncMock) -> None:
    with patch("api.redis_ops.lua_scripts") as mock_lua:
        mock_lua.decrement_stock = AsyncMock(return_value=0)
        result = await decrement_stock(redis, "product-A")
    assert result is False


async def test_decrement_stock_returns_false_when_lua_returns_minus_1(redis: AsyncMock) -> None:
    """Key missing (-1) → treated same as sold out → False."""
    with patch("api.redis_ops.lua_scripts") as mock_lua:
        mock_lua.decrement_stock = AsyncMock(return_value=-1)
        result = await decrement_stock(redis, "product-A")
    assert result is False


async def test_decrement_stock_passes_correct_stock_key(redis: AsyncMock) -> None:
    """Stock key must be 'stock:<product_id>'."""
    with patch("api.redis_ops.lua_scripts") as mock_lua:
        mock_lua.decrement_stock = AsyncMock(return_value=1)
        await decrement_stock(redis, "product-A")
        key_passed = mock_lua.decrement_stock.call_args[0][1]
    assert key_passed == "stock:product-A"


async def test_decrement_stock_calls_lua_once(redis: AsyncMock) -> None:
    with patch("api.redis_ops.lua_scripts") as mock_lua:
        mock_lua.decrement_stock = AsyncMock(return_value=1)
        await decrement_stock(redis, "product-A")
        mock_lua.decrement_stock.assert_awaited_once()


# ===========================================================================
# claim_idempotency — SET NX
# ===========================================================================


async def test_claim_idempotency_returns_true_when_set_nx_succeeds(redis: AsyncMock) -> None:
    """SET NX returns non-None → key was free → claimed."""
    redis.set.return_value = True
    result = await claim_idempotency(redis, "user-1", "key-123")
    assert result is True


async def test_claim_idempotency_returns_false_when_set_nx_fails(redis: AsyncMock) -> None:
    """SET NX returns None → key already exists → duplicate."""
    redis.set.return_value = None
    result = await claim_idempotency(redis, "user-1", "key-123")
    assert result is False


async def test_claim_idempotency_key_is_user_scoped(redis: AsyncMock) -> None:
    """Key must be 'idempotency:<user_id>:<key>'."""
    redis.set.return_value = True
    await claim_idempotency(redis, "alice", "my-key-abc")
    key_arg = redis.set.call_args[0][0]
    assert key_arg == "idempotency:alice:my-key-abc"


async def test_claim_idempotency_stores_pending_sentinel(redis: AsyncMock) -> None:
    """Value stored must be 'pending'."""
    redis.set.return_value = True
    await claim_idempotency(redis, "user-1", "key-123")
    value_arg = redis.set.call_args[0][1]
    assert value_arg == "pending"


async def test_claim_idempotency_uses_nx_flag(redis: AsyncMock) -> None:
    redis.set.return_value = True
    await claim_idempotency(redis, "user-1", "key-123")
    kwargs = redis.set.call_args[1]
    assert kwargs.get("nx") is True


async def test_claim_idempotency_has_ttl(redis: AsyncMock) -> None:
    redis.set.return_value = True
    await claim_idempotency(redis, "user-1", "key-123")
    kwargs = redis.set.call_args[1]
    assert "ex" in kwargs
    assert kwargs["ex"] == settings.idempotency_ttl_seconds


async def test_claim_idempotency_different_users_independent(redis: AsyncMock) -> None:
    redis.set.return_value = True
    await claim_idempotency(redis, "alice", "same-key-abcdef")
    await claim_idempotency(redis, "bob", "same-key-abcdef")

    key_alice = redis.set.call_args_list[0][0][0]
    key_bob = redis.set.call_args_list[1][0][0]
    assert key_alice != key_bob
    assert "alice" in key_alice
    assert "bob" in key_bob


# ===========================================================================
# resolve_idempotency — SET (overwrite)
# ===========================================================================


async def test_resolve_idempotency_calls_set(redis: AsyncMock) -> None:
    await resolve_idempotency(redis, "user-1", "key-123", "order-uuid-abc")
    redis.set.assert_awaited_once()


async def test_resolve_idempotency_stores_order_id(redis: AsyncMock) -> None:
    await resolve_idempotency(redis, "user-1", "key-123", "order-uuid-abc")
    value_arg = redis.set.call_args[0][1]
    assert value_arg == "order-uuid-abc"


async def test_resolve_idempotency_key_is_user_scoped(redis: AsyncMock) -> None:
    await resolve_idempotency(redis, "alice", "key-xyz", "order-1")
    key_arg = redis.set.call_args[0][0]
    assert key_arg == "idempotency:alice:key-xyz"


async def test_resolve_idempotency_has_ttl(redis: AsyncMock) -> None:
    await resolve_idempotency(redis, "user-1", "key-123", "order-1")
    kwargs = redis.set.call_args[1]
    assert "ex" in kwargs
    assert kwargs["ex"] == settings.idempotency_ttl_seconds


async def test_resolve_idempotency_does_not_use_nx(redis: AsyncMock) -> None:
    """Resolve overwrites — must NOT use nx=True."""
    await resolve_idempotency(redis, "user-1", "key-123", "order-1")
    kwargs = redis.set.call_args[1]
    assert "nx" not in kwargs


# ===========================================================================
# release_idempotency — DELETE
# ===========================================================================


async def test_release_idempotency_calls_delete(redis: AsyncMock) -> None:
    await release_idempotency(redis, "user-1", "key-123")
    redis.delete.assert_awaited_once()


async def test_release_idempotency_deletes_correct_key(redis: AsyncMock) -> None:
    await release_idempotency(redis, "alice", "key-abc")
    key_arg = redis.delete.call_args[0][0]
    assert key_arg == "idempotency:alice:key-abc"


# ===========================================================================
# get_idempotency — GET
# ===========================================================================


async def test_get_idempotency_returns_none_when_missing(redis: AsyncMock) -> None:
    redis.get.return_value = None
    result = await get_idempotency(redis, "user-1", "key-123")
    assert result is None


async def test_get_idempotency_returns_stored_order_id(redis: AsyncMock) -> None:
    redis.get.return_value = "order-uuid-abc"
    result = await get_idempotency(redis, "user-1", "key-123")
    assert result == "order-uuid-abc"


async def test_get_idempotency_returns_pending_sentinel(redis: AsyncMock) -> None:
    redis.get.return_value = "pending"
    result = await get_idempotency(redis, "user-1", "key-123")
    assert result == "pending"


async def test_get_idempotency_key_is_user_scoped(redis: AsyncMock) -> None:
    redis.get.return_value = None
    await get_idempotency(redis, "alice", "key-xyz")
    redis.get.assert_awaited_once_with("idempotency:alice:key-xyz")


# ===========================================================================
# enqueue_order — XADD
# ===========================================================================


async def test_enqueue_order_calls_xadd(redis: AsyncMock) -> None:
    redis.xadd.return_value = "1234-0"
    await enqueue_order(redis, order_id="o1", user_id="u1", product_id="p1")
    redis.xadd.assert_awaited_once()


async def test_enqueue_order_stream_name(redis: AsyncMock) -> None:
    """Stream name must be 'orders' (settings.orders_stream)."""
    redis.xadd.return_value = "1234-0"
    await enqueue_order(redis, order_id="o1", user_id="u1", product_id="p1")
    stream_name = redis.xadd.call_args[0][0]
    assert stream_name == "orders"


async def test_enqueue_order_payload_fields(redis: AsyncMock) -> None:
    """Payload must contain order_id, user_id, product_id."""
    redis.xadd.return_value = "1234-0"
    await enqueue_order(redis, order_id="o1", user_id="u1", product_id="p1")
    payload = redis.xadd.call_args[0][1]
    assert payload["order_id"] == "o1"
    assert payload["user_id"] == "u1"
    assert payload["product_id"] == "p1"


async def test_enqueue_order_uses_approximate_maxlen(redis: AsyncMock) -> None:
    """XADD must use maxlen with approximate=True for O(1) trimming."""
    redis.xadd.return_value = "1234-0"
    await enqueue_order(redis, order_id="o1", user_id="u1", product_id="p1")
    kwargs = redis.xadd.call_args[1]
    assert kwargs.get("approximate") is True
    assert "maxlen" in kwargs
