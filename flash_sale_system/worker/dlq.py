"""
Dead-letter queue for the flash-sale worker.

When all retry attempts are exhausted, the failed message is written to a
separate Redis Stream (orders.dlq) with the original payload plus failure
metadata. The original message is then XACK'd so it leaves the PEL and
doesn't block processing of subsequent messages.

DLQ entry fields:
  order_id, user_id, product_id, timestamp  — original OrderEvent fields
  version                                    — original schema version
  failed_at                                  — ISO-8601 UTC time of failure
  error                                      — last exception string
  original_msg_id                            — source stream message ID
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from shared.config import settings
from shared.stream_schema import OrderEvent

logger = logging.getLogger(__name__)


async def send_to_dlq(
    redis: Redis,  # type: ignore[type-arg]
    *,
    msg_id: str,
    event: OrderEvent,
    error: str,
) -> None:
    """
    Write a failed message to the DLQ stream and XACK the original.

    The XADD + XACK are not atomic, but that's acceptable:
    - If XADD succeeds and XACK fails → message re-enters DLQ on next reclaim
      (DLQ entry will be a duplicate, which is harmless)
    - If XADD fails → exception propagates, original stays in PEL for retry
    """
    dlq_entry = {
        **event.to_dict(),
        "failed_at": datetime.now(tz=UTC).isoformat(),
        "error": error[:500],  # cap length to avoid huge Redis values
        "original_msg_id": msg_id,
    }

    await redis.xadd(settings.dlq_stream, dlq_entry)
    await redis.xack(settings.orders_stream, settings.orders_consumer_group, msg_id)

    logger.error(
        "message_sent_to_dlq",
        extra={
            "order_id": event.order_id,
            "original_msg_id": msg_id,
            "error": error,
        },
    )
