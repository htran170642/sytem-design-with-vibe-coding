"""
Unit tests for worker.dlq.send_to_dlq — mocked Redis, no real connection.

Covers:
- XADD is called on the DLQ stream
- XACK is called on the original stream
- DLQ entry contains all required fields
- Error message is capped at 500 characters
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from shared.stream_schema import OrderEvent
from worker.dlq import send_to_dlq

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis() -> AsyncMock:
    r = AsyncMock()
    r.xadd.return_value = "1000-0"
    return r


def _make_event() -> OrderEvent:
    return OrderEvent.create(
        order_id=str(uuid.uuid4()),
        user_id="user-1",
        product_id="prod-1",
    )


# ===========================================================================
# XADD behaviour
# ===========================================================================


async def test_send_to_dlq_calls_xadd(redis: AsyncMock) -> None:
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error="db error")
    redis.xadd.assert_awaited_once()


async def test_send_to_dlq_writes_to_dlq_stream(redis: AsyncMock) -> None:
    """Must write to 'orders.dlq', not the main stream."""
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error="err")

    stream_name = redis.xadd.call_args[0][0]
    assert stream_name == "orders.dlq"


async def test_send_to_dlq_entry_contains_order_fields(redis: AsyncMock) -> None:
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error="err")

    payload = redis.xadd.call_args[0][1]
    assert payload["order_id"] == event.order_id
    assert payload["user_id"] == event.user_id
    assert payload["product_id"] == event.product_id


async def test_send_to_dlq_entry_contains_failure_metadata(redis: AsyncMock) -> None:
    event = _make_event()
    await send_to_dlq(redis, msg_id="9999-0", event=event, error="something broke")

    payload = redis.xadd.call_args[0][1]
    assert "failed_at" in payload
    assert payload["error"] == "something broke"
    assert payload["original_msg_id"] == "9999-0"


async def test_send_to_dlq_error_capped_at_500_chars(redis: AsyncMock) -> None:
    """Very long error strings must be truncated to 500 chars."""
    long_error = "x" * 1000
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error=long_error)

    payload = redis.xadd.call_args[0][1]
    assert len(payload["error"]) == 500


async def test_send_to_dlq_short_error_not_truncated(redis: AsyncMock) -> None:
    short_error = "db timeout"
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error=short_error)

    payload = redis.xadd.call_args[0][1]
    assert payload["error"] == short_error


# ===========================================================================
# XACK behaviour
# ===========================================================================


async def test_send_to_dlq_calls_xack(redis: AsyncMock) -> None:
    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error="err")
    redis.xack.assert_awaited_once()


async def test_send_to_dlq_xack_uses_correct_stream_and_group(redis: AsyncMock) -> None:
    """XACK must target the main orders stream, not the DLQ."""
    event = _make_event()
    await send_to_dlq(redis, msg_id="5555-0", event=event, error="err")

    args = redis.xack.call_args[0]
    stream, group, msg_id = args[0], args[1], args[2]
    assert stream == "orders"
    assert group == "order-workers"
    assert msg_id == "5555-0"


async def test_send_to_dlq_xadd_before_xack(redis: AsyncMock) -> None:
    """
    XADD must be called before XACK.
    If XADD fails, the message stays in PEL for retry — safe.
    If XADD succeeds and XACK fails → duplicate DLQ entry on re-delivery — harmless.
    """
    call_order: list[str] = []

    async def xadd_side_effect(*a, **kw) -> str:
        call_order.append("xadd")
        return "1-0"

    async def xack_side_effect(*a, **kw) -> int:
        call_order.append("xack")
        return 1

    redis.xadd.side_effect = xadd_side_effect
    redis.xack.side_effect = xack_side_effect

    event = _make_event()
    await send_to_dlq(redis, msg_id="1000-0", event=event, error="err")

    assert call_order == ["xadd", "xack"]
