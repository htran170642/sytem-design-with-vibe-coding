"""
Redis Stream consumer for the flash-sale worker.

Responsibilities:
  - XAUTOCLAIM stale messages on startup (crash recovery)
  - XREADGROUP in a tight loop to pick up new messages
  - Yield OrderEvents to the caller for processing
  - XACK only after the caller confirms success
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from shared.config import settings
from shared.stream_schema import OrderEvent

logger = logging.getLogger(__name__)


class StreamConsumer:
    """
    Wraps XREADGROUP + XAUTOCLAIM into a simple async iterator.

    Usage:
        consumer = StreamConsumer(redis)
        async for msg_id, event in consumer.messages():
            await process(event)
            await consumer.ack(msg_id)
    """

    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis
        self._stream = settings.orders_stream
        self._group = settings.orders_consumer_group
        self._consumer = settings.worker_consumer_name
        self._claim_idle_ms = settings.stream_claim_min_idle_ms

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def messages(self) -> AsyncIterator[tuple[str, OrderEvent]]:
        """
        Yield (message_id, OrderEvent) pairs indefinitely.

        On first call: reclaims any stale messages from crashed workers.
        Then: polls for new messages with a 2-second blocking read.
        """
        # Reclaim stale pending messages from dead consumers first
        async for msg_id, event in self._reclaim_stale():
            yield msg_id, event

        # Main poll loop
        while True:
            async for msg_id, event in self._read_new():
                yield msg_id, event

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a successfully processed message."""
        await self._redis.xack(self._stream, self._group, msg_id)
        logger.debug("acked", extra={"msg_id": msg_id})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _reclaim_stale(self) -> AsyncIterator[tuple[str, OrderEvent]]:
        """
        XAUTOCLAIM: take ownership of messages idle longer than claim_idle_ms.
        Handles messages left unacked by a crashed worker instance.
        """
        cursor = "0-0"
        while True:
            result = await self._redis.xautoclaim(
                self._stream,
                self._group,
                self._consumer,
                min_idle_time=self._claim_idle_ms,
                start_id=cursor,
                count=100,
            )
            # result = (next_cursor, [(id, fields), ...], [deleted_ids])
            next_cursor, entries, _ = result

            for msg_id, fields in entries:
                try:
                    event = OrderEvent.from_dict(fields)
                    logger.info("reclaimed_message", extra={"msg_id": msg_id})
                    yield msg_id, event
                except (KeyError, ValueError) as exc:
                    logger.error(
                        "malformed_reclaimed_message",
                        extra={"msg_id": msg_id, "error": str(exc)},
                    )
                    await self.ack(msg_id)  # discard unreadable message

            if next_cursor == "0-0":
                break
            cursor = next_cursor

    async def _read_new(self) -> AsyncIterator[tuple[str, OrderEvent]]:
        """
        XREADGROUP: read new messages not yet delivered to any consumer.
        Blocks for up to 2 seconds waiting for messages (avoids busy loop).
        """
        results = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=10,
            block=2000,  # ms — yields control back every 2s if idle
        )

        if not results:
            await asyncio.sleep(0)  # yield to event loop
            return

        for _stream_name, entries in results:
            for msg_id, fields in entries:
                try:
                    event = OrderEvent.from_dict(fields)
                    logger.debug("received_message", extra={"msg_id": msg_id})
                    yield msg_id, event
                except (KeyError, ValueError) as exc:
                    logger.error(
                        "malformed_message",
                        extra={"msg_id": msg_id, "error": str(exc)},
                    )
                    await self.ack(msg_id)  # discard unreadable message
