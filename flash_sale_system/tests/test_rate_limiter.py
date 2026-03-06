"""
Unit tests for RateLimiter — mocked Redis client.

We verify:
- Correct boolean return value based on Lua result
- Correct Redis key format
- Limit value is passed through to the Lua script
"""

import time
from unittest.mock import AsyncMock

import pytest

from api.rate_limiter import RateLimiter


@pytest.fixture
def redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def limiter(redis: AsyncMock) -> RateLimiter:
    return RateLimiter(redis)


# ---------------------------------------------------------------------------
# allow_user
# ---------------------------------------------------------------------------


async def test_allow_user_returns_true_when_lua_returns_1(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    redis.eval.return_value = 1
    assert await limiter.allow_user("alice") is True


async def test_allow_user_returns_false_when_lua_returns_0(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    """Lua returns 0 → over limit → rejected."""
    redis.eval.return_value = 0
    assert await limiter.allow_user("alice") is False


async def test_allow_user_key_contains_user_id(redis: AsyncMock, limiter: RateLimiter) -> None:
    """Key must be 'rl:user:<user_id>' so different users have separate counters."""
    redis.eval.return_value = 1
    await limiter.allow_user("alice")

    # eval(script, numkeys, key, limit)  →  positional args[2] is the key
    key = redis.eval.call_args[0][2]
    assert key == "rl:user:alice"


async def test_allow_user_different_users_use_different_keys(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    redis.eval.return_value = 1
    await limiter.allow_user("alice")
    await limiter.allow_user("bob")

    first_key = redis.eval.call_args_list[0][0][2]
    second_key = redis.eval.call_args_list[1][0][2]
    assert first_key == "rl:user:alice"
    assert second_key == "rl:user:bob"


async def test_allow_user_passes_limit_to_lua(redis: AsyncMock, limiter: RateLimiter) -> None:
    """The limit from settings must be passed as ARGV[1] in the Lua call."""
    redis.eval.return_value = 1
    await limiter.allow_user("alice")

    # eval(script, numkeys, key, limit)  →  positional args[3] is the limit
    limit_passed = redis.eval.call_args[0][3]
    assert limit_passed == 10  # default from settings.rate_limit_per_user


async def test_allow_user_calls_eval_once_per_request(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    redis.eval.return_value = 1
    await limiter.allow_user("alice")
    redis.eval.assert_awaited_once()


# ---------------------------------------------------------------------------
# allow_global
# ---------------------------------------------------------------------------


async def test_allow_global_returns_true_when_lua_returns_1(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    redis.eval.return_value = 1
    assert await limiter.allow_global() is True


async def test_allow_global_returns_false_when_lua_returns_0(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    redis.eval.return_value = 0
    assert await limiter.allow_global() is False


async def test_allow_global_key_contains_epoch_second(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    """Key must be 'rl:global:<epoch_second>' — window aligned to wall clock."""
    redis.eval.return_value = 1
    before = int(time.time())
    await limiter.allow_global()
    after = int(time.time())

    key = redis.eval.call_args[0][2]
    assert key.startswith("rl:global:")

    epoch_in_key = int(key.split(":")[-1])
    assert before <= epoch_in_key <= after


async def test_allow_global_passes_limit_to_lua(redis: AsyncMock, limiter: RateLimiter) -> None:
    redis.eval.return_value = 1
    await limiter.allow_global()

    limit_passed = redis.eval.call_args[0][3]
    assert limit_passed == 100_000  # default from settings.rate_limit_global


async def test_allow_global_same_key_within_same_second(
    redis: AsyncMock, limiter: RateLimiter
) -> None:
    """Two calls within the same second must hit the same Redis key."""
    redis.eval.return_value = 1
    await limiter.allow_global()
    await limiter.allow_global()

    key1 = redis.eval.call_args_list[0][0][2]
    key2 = redis.eval.call_args_list[1][0][2]
    assert key1 == key2
