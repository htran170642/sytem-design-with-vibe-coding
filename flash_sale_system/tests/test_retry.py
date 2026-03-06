"""
Unit tests for worker.retry — pure Python + asyncio, no external dependencies.

Covers:
- _backoff_delay  pure math function
- with_retry      success, transient retry, permanent raise, exhaustion
"""

from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from worker.retry import _backoff_delay, with_retry

# ===========================================================================
# _backoff_delay
# ===========================================================================


def test_backoff_attempt_0_returns_base() -> None:
    """First attempt: delay = base * 2^0 = base (before jitter)."""
    # Without jitter (patch random to 0.5 → jitter = 0)
    with patch("worker.retry.random.random", return_value=0.5):
        delay = _backoff_delay(attempt=0, base=1.0, cap=60.0)
    assert delay == pytest.approx(1.0, rel=0.01)


def test_backoff_attempt_1_doubles() -> None:
    """Second attempt: base * 2^1 = 2.0."""
    with patch("worker.retry.random.random", return_value=0.5):
        delay = _backoff_delay(attempt=1, base=1.0, cap=60.0)
    assert delay == pytest.approx(2.0, rel=0.01)


def test_backoff_capped_at_max_delay() -> None:
    """Delay is capped at max_delay regardless of attempt number."""
    with patch("worker.retry.random.random", return_value=0.5):
        delay = _backoff_delay(attempt=100, base=1.0, cap=10.0)
    assert delay == pytest.approx(10.0, rel=0.01)


def test_backoff_never_negative() -> None:
    """Even with max negative jitter, delay must be >= 0."""
    with patch("worker.retry.random.random", return_value=0.0):
        delay = _backoff_delay(attempt=0, base=0.1, cap=60.0)
    assert delay >= 0.0


def test_backoff_jitter_range() -> None:
    """Jitter is ±20%, so delay is within [base*0.8, base*1.2] for attempt 0."""
    results = set()
    for seed in [0.0, 0.5, 1.0]:
        with patch("worker.retry.random.random", return_value=seed):
            d = _backoff_delay(attempt=0, base=1.0, cap=60.0)
        results.add(round(d, 6))
    # Should produce at least two distinct values (jitter is applied)
    assert len(results) >= 2


# ===========================================================================
# with_retry — success path
# ===========================================================================


async def test_with_retry_returns_result_on_first_success() -> None:
    fn = AsyncMock(return_value=42)
    result = await with_retry(fn, max_attempts=3)
    assert result == 42
    fn.assert_awaited_once()


async def test_with_retry_calls_fn_once_on_success() -> None:
    fn = AsyncMock(return_value="ok")
    await with_retry(fn, max_attempts=5)
    assert fn.await_count == 1


# ===========================================================================
# with_retry — transient errors (retried)
# ===========================================================================


async def test_with_retry_retries_on_transient_error() -> None:
    """Fails twice with OSError, succeeds on third attempt."""
    fn = AsyncMock(side_effect=[OSError("timeout"), OSError("timeout"), "success"])
    result = await with_retry(fn, max_attempts=3, base_delay=0.0)
    assert result == "success"
    assert fn.await_count == 3


async def test_with_retry_raises_after_max_attempts_exhausted() -> None:
    """All attempts fail with transient error → raises last exception."""
    fn = AsyncMock(side_effect=OSError("connection refused"))
    with pytest.raises(OSError, match="connection refused"):
        await with_retry(fn, max_attempts=3, base_delay=0.0)
    assert fn.await_count == 3


async def test_with_retry_raises_asyncpg_connection_failure() -> None:
    fn = AsyncMock(side_effect=asyncpg.ConnectionFailureError("db down"))
    with pytest.raises(asyncpg.ConnectionFailureError):
        await with_retry(fn, max_attempts=2, base_delay=0.0)
    assert fn.await_count == 2


# ===========================================================================
# with_retry — permanent errors (NOT retried)
# ===========================================================================


async def test_with_retry_raises_immediately_on_unique_violation() -> None:
    """UniqueViolationError is permanent — must not retry."""
    fn = AsyncMock(side_effect=asyncpg.UniqueViolationError("duplicate key"))
    with pytest.raises(asyncpg.UniqueViolationError):
        await with_retry(fn, max_attempts=5, base_delay=0.0)
    # Only called once — no retry
    fn.assert_awaited_once()


async def test_with_retry_raises_immediately_on_not_null_violation() -> None:
    fn = AsyncMock(side_effect=asyncpg.NotNullViolationError("null value"))
    with pytest.raises(asyncpg.NotNullViolationError):
        await with_retry(fn, max_attempts=5, base_delay=0.0)
    fn.assert_awaited_once()


async def test_with_retry_raises_immediately_on_undefined_table() -> None:
    fn = AsyncMock(side_effect=asyncpg.UndefinedTableError("no table"))
    with pytest.raises(asyncpg.UndefinedTableError):
        await with_retry(fn, max_attempts=5, base_delay=0.0)
    fn.assert_awaited_once()


# ===========================================================================
# with_retry — unknown errors (treated as transient)
# ===========================================================================


async def test_with_retry_retries_on_unknown_exception() -> None:
    """Unexpected exceptions are treated as transient — retried until exhausted."""
    fn = AsyncMock(side_effect=ValueError("unexpected"))
    with pytest.raises(ValueError, match="unexpected"):
        await with_retry(fn, max_attempts=3, base_delay=0.0)
    assert fn.await_count == 3


async def test_with_retry_recovers_from_unknown_then_succeeds() -> None:
    fn = AsyncMock(side_effect=[ValueError("blip"), "recovered"])
    result = await with_retry(fn, max_attempts=3, base_delay=0.0)
    assert result == "recovered"
    assert fn.await_count == 2


# ===========================================================================
# with_retry — attempt counting
# ===========================================================================


async def test_with_retry_respects_max_attempts_1() -> None:
    """max_attempts=1 → no retry, raises immediately on first failure."""
    fn = AsyncMock(side_effect=OSError("fail"))
    with pytest.raises(OSError):
        await with_retry(fn, max_attempts=1, base_delay=0.0)
    fn.assert_awaited_once()
