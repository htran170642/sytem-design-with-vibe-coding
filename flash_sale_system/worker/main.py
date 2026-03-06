"""
Flash-sale worker entry point.

Lifecycle:
  1. Connect to Redis + PostgreSQL
  2. Process messages from the orders stream indefinitely
  3. On SIGTERM/SIGINT: stop accepting new messages, finish current one, exit cleanly

Run:
    python -m worker.main
"""

from __future__ import annotations

import asyncio
import logging
import signal

import redis.asyncio as aioredis
import structlog as _structlog

from api.redis_ops import setup_stream
from shared.config import settings
from shared.logging import configure_logging
from shared.lua_scripts import LuaScripts
from shared.metrics import ORDERS_PROCESSED
from worker.consumer import StreamConsumer
from worker.db import close_db_pool, init_db_pool, insert_order
from worker.dlq import send_to_dlq
from worker.retry import with_retry

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self) -> None:
        self._shutdown = asyncio.Event()

    def request_shutdown(self) -> None:
        logger.info("shutdown_requested")
        self._shutdown.set()

    async def run(self) -> None:
        configure_logging()

        # --- Connect ---
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        scripts = LuaScripts()
        await scripts.load(redis)
        await setup_stream(redis)
        await init_db_pool()
        logger.info(
            "worker_started",
            extra={
                "consumer": settings.worker_consumer_name,
                "stream": settings.orders_stream,
                "group": settings.orders_consumer_group,
            },
        )

        consumer = StreamConsumer(redis)

        try:
            async for msg_id, event in consumer.messages():
                # Stop accepting new messages after shutdown signal
                if self._shutdown.is_set():
                    # Put this message back by NOT acking — PEL will redeliver it
                    logger.info("shutdown_skip_message", extra={"msg_id": msg_id})
                    break

                await self._process(redis, consumer, msg_id, event)

        finally:
            await redis.aclose()  # type: ignore[attr-defined]
            await close_db_pool()
            logger.info("worker_stopped")

    async def _process(
        self,
        redis: aioredis.Redis,  # type: ignore[type-arg]
        consumer: StreamConsumer,
        msg_id: str,
        event: object,
    ) -> None:
        from shared.stream_schema import OrderEvent

        assert isinstance(event, OrderEvent)

        # Bind correlation IDs so every log line during this message's processing
        # automatically includes order_id and msg_id (same pattern as request_id in API).
        _structlog.contextvars.clear_contextvars()
        _structlog.contextvars.bind_contextvars(order_id=event.order_id, msg_id=msg_id)

        log = logger.getChild("process")

        try:
            await with_retry(
                lambda: insert_order(event),
                max_attempts=3,
                base_delay=0.5,
                max_delay=10.0,
                label=event.order_id,
            )
            await consumer.ack(msg_id)
            log.info("processed", extra={"order_id": event.order_id, "msg_id": msg_id})

        except Exception as exc:
            # All retries exhausted — move to DLQ so the stream keeps moving
            log.error(
                "processing_failed_sending_to_dlq",
                extra={"order_id": event.order_id, "error": str(exc)},
            )
            ORDERS_PROCESSED.labels(result="failed").inc()
            await send_to_dlq(redis, msg_id=msg_id, event=event, error=str(exc))


async def _main() -> None:
    worker = Worker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(_main())
