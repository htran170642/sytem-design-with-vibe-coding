"""
Unit tests for StreamConsumer — mocked Redis, no real connection needed.

Tests:
- ack()           calls XACK with correct args
- _read_new()     happy path, empty response, malformed message
- _reclaim_stale() no stale messages (cursor 0-0 immediately)
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from shared.stream_schema import OrderEvent
from worker.consumer import StreamConsumer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis() -> AsyncMock:
    r = AsyncMock()
    # Default: empty responses (nothing to read / reclaim)
    r.xreadgroup.return_value = []
    r.xautoclaim.return_value = ("0-0", [], [])
    return r


@pytest.fixture
def consumer(redis: AsyncMock) -> StreamConsumer:
    return StreamConsumer(redis)


def _make_event(
    user_id: str = "user-1",
    product_id: str = "prod-1",
) -> OrderEvent:
    return OrderEvent.create(
        order_id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id,
    )


# ===========================================================================
# ack()
# ===========================================================================


async def test_ack_calls_xack(redis: AsyncMock, consumer: StreamConsumer) -> None:
    await consumer.ack("1234-0")
    redis.xack.assert_awaited_once()


async def test_ack_passes_correct_stream_and_group(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    await consumer.ack("9999-0")
    call_args = redis.xack.call_args[0]
    stream = call_args[0]
    group = call_args[1]
    msg_id = call_args[2]
    assert stream == "orders"
    assert group == "order-workers"
    assert msg_id == "9999-0"


# ===========================================================================
# _read_new()
# ===========================================================================


async def test_read_new_yields_nothing_when_empty(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    redis.xreadgroup.return_value = []
    results = [x async for x in consumer._read_new()]
    assert results == []


async def test_read_new_yields_event_from_valid_entry(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    event = _make_event()
    raw_fields = event.to_dict()
    redis.xreadgroup.return_value = [("orders", [("1000-0", raw_fields)])]

    results = [x async for x in consumer._read_new()]

    assert len(results) == 1
    msg_id, received_event = results[0]
    assert msg_id == "1000-0"
    assert received_event == event


async def test_read_new_yields_multiple_events(redis: AsyncMock, consumer: StreamConsumer) -> None:
    events = [_make_event(user_id=f"user-{i}") for i in range(3)]
    entries = [(f"{i + 1}000-0", e.to_dict()) for i, e in enumerate(events)]
    redis.xreadgroup.return_value = [("orders", entries)]

    results = [x async for x in consumer._read_new()]
    assert len(results) == 3


async def test_read_new_acks_and_discards_malformed_message(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    """A message missing required fields is discarded (acked) without raising."""
    redis.xreadgroup.return_value = [("orders", [("5000-0", {"bad": "data"})])]

    results = [x async for x in consumer._read_new()]

    # Malformed entry is discarded — not yielded
    assert results == []
    # It IS acked so it doesn't block the consumer
    redis.xack.assert_awaited_once()


# ===========================================================================
# _reclaim_stale()
# ===========================================================================


async def test_reclaim_stale_does_nothing_when_no_stale_messages(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    """cursor '0-0' with empty list → loop exits immediately."""
    redis.xautoclaim.return_value = ("0-0", [], [])

    results = [x async for x in consumer._reclaim_stale()]

    assert results == []
    redis.xautoclaim.assert_awaited_once()


async def test_reclaim_stale_yields_valid_events(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    event = _make_event()
    redis.xautoclaim.return_value = (
        "0-0",  # final cursor → stop after one call
        [("2000-0", event.to_dict())],  # one stale entry
        [],
    )

    results = [x async for x in consumer._reclaim_stale()]

    assert len(results) == 1
    msg_id, received = results[0]
    assert msg_id == "2000-0"
    assert received == event


async def test_reclaim_stale_acks_malformed_entries(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    """Unreadable stale message is acked and discarded."""
    redis.xautoclaim.return_value = (
        "0-0",
        [("7777-0", {"garbage": "yes"})],
        [],
    )

    results = [x async for x in consumer._reclaim_stale()]

    assert results == []
    redis.xack.assert_awaited_once()


async def test_reclaim_stale_paginates_until_cursor_is_zero(
    redis: AsyncMock, consumer: StreamConsumer
) -> None:
    """When cursor != '0-0', consumer should make another XAUTOCLAIM call."""
    event1 = _make_event(user_id="user-A")
    event2 = _make_event(user_id="user-B")

    redis.xautoclaim.side_effect = [
        # First call: non-zero cursor → continue
        ("3000-0", [("1000-0", event1.to_dict())], []),
        # Second call: cursor is 0-0 → stop
        ("0-0", [("2000-0", event2.to_dict())], []),
    ]

    results = [x async for x in consumer._reclaim_stale()]

    assert len(results) == 2
    assert redis.xautoclaim.await_count == 2
