"""
Rate limiting using Redis.

Per-user: token bucket (sliding refill via INCR + TTL).
Global:   simple fixed-window counter.

Both checks are atomic Lua scripts.
"""

from redis.asyncio import Redis

from shared.config import settings

# ---------------------------------------------------------------------------
# Per-user token bucket (Lua)
# Keys: rl:user:<user_id>
# Each key holds the number of requests consumed in the current window.
# Window = 1 second; limit = settings.rate_limit_per_user.
# ---------------------------------------------------------------------------
_USER_BUCKET_LUA = """
local key   = KEYS[1]
local limit = tonumber(ARGV[1])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, 1)
end
if current > limit then
    return 0
end
return 1
"""

# ---------------------------------------------------------------------------
# Global fixed-window counter (Lua)
# Keys: rl:global:<epoch_second>
# ---------------------------------------------------------------------------
_GLOBAL_COUNTER_LUA = """
local key   = KEYS[1]
local limit = tonumber(ARGV[1])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, 1)
end
if current > limit then
    return 0
end
return 1
"""


class RateLimiter:
    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis

    async def allow_user(self, user_id: str) -> bool:
        key = f"rl:user:{user_id}"
        result: int = await self._redis.eval(  # type: ignore[misc]
            _USER_BUCKET_LUA, 1, key, settings.rate_limit_per_user
        )
        return result == 1

    async def allow_global(self) -> bool:
        import time

        key = f"rl:global:{int(time.time())}"
        result: int = await self._redis.eval(  # type: ignore[misc]
            _GLOBAL_COUNTER_LUA, 1, key, settings.rate_limit_global
        )
        return result == 1
