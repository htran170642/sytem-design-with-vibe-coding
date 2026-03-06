"""
Exponential backoff retry for the worker's DB write path.

Strategy:
  - Attempt up to max_attempts times
  - Wait base_delay * 2^attempt seconds between retries (capped at max_delay)
  - Add jitter (±20%) to avoid thundering herd when many workers retry together
  - Only retry on transient errors (connection issues, timeouts)
  - Raise immediately on permanent errors (unique violation is handled upstream)
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Errors that are worth retrying
_TRANSIENT = (
    asyncpg.TooManyConnectionsError,
    asyncpg.ConnectionFailureError,
    asyncpg.ConnectionDoesNotExistError,
    asyncpg.PostgresConnectionError,
    OSError,
    TimeoutError,
)

# Errors that should never be retried — caller handles them
_PERMANENT = (
    asyncpg.UniqueViolationError,
    asyncpg.NotNullViolationError,
    asyncpg.ForeignKeyViolationError,
    asyncpg.UndefinedTableError,
)


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    """Return jittered exponential delay for the given attempt number (0-indexed)."""
    delay = min(base * (2**attempt), cap)
    jitter = delay * 0.2 * (random.random() * 2 - 1)  # ±20%  # noqa: S311
    return max(0.0, delay + jitter)


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,  # seconds
    max_delay: float = 10.0,  # seconds
    label: str = "operation",
) -> T:
    """
    Call fn() up to max_attempts times with exponential backoff.

    Raises the last exception if all attempts are exhausted.
    Raises immediately on permanent (non-retryable) errors.
    """
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await fn()

        except _PERMANENT as exc:
            # Permanent errors — no point retrying
            logger.warning(
                "retry_permanent_error",
                extra={"label": label, "error": str(exc)},
            )
            raise

        except _TRANSIENT as exc:
            last_exc = exc
            if attempt + 1 == max_attempts:
                break

            delay = _backoff_delay(attempt, base_delay, max_delay)
            logger.warning(
                "retry_transient_error",
                extra={
                    "label": label,
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "retry_in": round(delay, 2),
                    "error": str(exc),
                },
            )
            await asyncio.sleep(delay)

        except Exception as exc:
            # Unknown error — treat as transient but log loudly
            last_exc = exc
            if attempt + 1 == max_attempts:
                break

            delay = _backoff_delay(attempt, base_delay, max_delay)
            logger.error(
                "retry_unknown_error",
                extra={
                    "label": label,
                    "attempt": attempt + 1,
                    "retry_in": round(delay, 2),
                    "error": str(exc),
                },
            )
            await asyncio.sleep(delay)

    logger.error(
        "retry_exhausted",
        extra={"label": label, "attempts": max_attempts, "error": str(last_exc)},
    )
    raise last_exc  # type: ignore[misc]
