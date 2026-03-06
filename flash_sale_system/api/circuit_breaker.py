"""
Simple in-process circuit breaker for Redis calls.

States: CLOSED → OPEN → HALF_OPEN → CLOSED
- CLOSED: normal operation
- OPEN: fast-fail for `recovery_timeout` seconds after `failure_threshold` failures
- HALF_OPEN: one probe allowed; success closes, failure reopens
"""

import time
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 10.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at: float = 0.0

    @property
    def state(self) -> State:
        if self._state is State.OPEN:
            if time.monotonic() - self._opened_at >= self._recovery_timeout:
                self._state = State.HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        return self.state is State.OPEN

    def record_success(self) -> None:
        self._failures = 0
        if self._state is not State.CLOSED:
            logger.info("circuit_breaker_closed")
        self._state = State.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._state is State.HALF_OPEN:
            # Probe failed — go straight back to OPEN, reset the recovery clock
            self._state = State.OPEN
            self._opened_at = time.monotonic()
            logger.warning("circuit_breaker_reopened_from_half_open")
        elif self._failures >= self._failure_threshold and self._state is State.CLOSED:
            self._state = State.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "circuit_breaker_opened",
                failures=self._failures,
                recovery_timeout=self._recovery_timeout,
            )


# Module-level singleton used by the buy route
redis_circuit_breaker = CircuitBreaker()
