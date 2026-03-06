"""
Unit tests for CircuitBreaker — pure Python, no Redis needed.

Tests every state transition in the CLOSED → OPEN → HALF_OPEN → CLOSED machine.
"""

import time

from api.circuit_breaker import CircuitBreaker, State

# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_state_is_closed() -> None:
    cb = CircuitBreaker()
    assert cb.state is State.CLOSED
    assert not cb.is_open()


# ---------------------------------------------------------------------------
# CLOSED behaviour
# ---------------------------------------------------------------------------


def test_success_keeps_closed() -> None:
    cb = CircuitBreaker()
    for _ in range(20):
        cb.record_success()
    assert cb.state is State.CLOSED


def test_single_failure_does_not_open() -> None:
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    assert cb.state is State.CLOSED
    assert not cb.is_open()


def test_opens_exactly_at_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.state is State.CLOSED  # still closed at 2

    cb.record_failure()
    assert cb.state is State.OPEN  # opens at 3
    assert cb.is_open()


def test_success_resets_failure_counter() -> None:
    """
    Failures must be *consecutive* to trip the breaker.
    A success in the middle resets the counter.
    """
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # resets to 0
    cb.record_failure()  # only 1 consecutive failure now
    cb.record_failure()  # 2 consecutive — still closed
    assert cb.state is State.CLOSED


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN transition
# ---------------------------------------------------------------------------


def test_open_stays_open_before_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
    cb.record_failure()
    assert cb.state is State.OPEN  # timeout not elapsed

    # Repeated checks don't change state
    assert cb.is_open()
    assert cb.state is State.OPEN


def test_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    cb.record_failure()
    assert cb.state is State.OPEN

    time.sleep(0.02)  # let recovery_timeout elapse
    assert cb.state is State.HALF_OPEN
    assert not cb.is_open()  # HALF_OPEN is not "open" — probe allowed


# ---------------------------------------------------------------------------
# HALF_OPEN behaviour
# ---------------------------------------------------------------------------


def test_success_from_half_open_closes() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    cb.record_failure()
    time.sleep(0.02)
    assert cb.state is State.HALF_OPEN

    cb.record_success()
    assert cb.state is State.CLOSED


def test_failure_from_half_open_reopens() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    cb.record_failure()
    time.sleep(0.02)
    assert cb.state is State.HALF_OPEN

    cb.record_failure()
    assert cb.state is State.OPEN
    assert cb.is_open()


# ---------------------------------------------------------------------------
# Multiple open/recover cycles
# ---------------------------------------------------------------------------


def test_full_cycle_closed_open_halfopen_closed() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)

    # Trip it
    cb.record_failure()
    cb.record_failure()
    assert cb.state is State.OPEN

    # Wait for recovery
    time.sleep(0.02)
    assert cb.state is State.HALF_OPEN

    # Probe succeeds
    cb.record_success()
    assert cb.state is State.CLOSED

    # Verify it works normally again
    cb.record_failure()
    assert cb.state is State.CLOSED  # needs 2 consecutive again
