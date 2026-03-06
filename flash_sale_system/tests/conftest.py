"""
Shared fixtures for all tests.

Strategy:
- mock_redis: an AsyncMock that mimics redis.asyncio.Redis
- client: httpx AsyncClient with the FastAPI app
  - lifespan Redis init/close are patched out (no real Redis needed)
  - get_redis dependency is overridden to return mock_redis
- reset_singletons (autouse): resets module-level state between tests

Happy-path mock call sequence for POST /buy:
  1. eval(lua, 1, "rl:user:<uid>", 10)          → 1  (user rate limiter)
  2. eval(lua, 1, "rl:global:<ts>", 100000)     → 1  (global rate limiter)
  3. set("idempotency:<uid>:<key>", "pending",
         nx=True, ex=86400)                      → True  (claim)
  4. evalsha(sha, 1, "stock:<product>")          → 1  (atomic decrement)
  5. xadd("orders", {...}, maxlen=..., ...)      → "1-0"
  6. set("idempotency:<uid>:<key>", order_id,
         ex=86400)                               → True  (resolve)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import api.routes.buy as buy_module
from api.circuit_breaker import State, redis_circuit_breaker
from api.dependencies import get_redis
from api.main import app
from shared.lua_scripts import lua_scripts


@pytest.fixture
def mock_redis() -> AsyncMock:
    """
    A fully mocked async Redis client.

    Default return values represent the "happy path":
      - ping:    True   (health check passes)
      - get:     None   (no cached idempotency value)
      - set:     True   (SET NX claim succeeds + resolve succeeds)
      - eval:    1      (rate limiters allow)
      - evalsha: 1      (stock decrement ok)
      - xadd:    "1-0"  (stream enqueue ok)
    """
    r = AsyncMock()
    r.ping.return_value = True
    r.get.return_value = None
    r.set.return_value = True  # NX claim returns non-None → claimed
    r.eval.return_value = 1
    r.evalsha.return_value = 1  # stock decrement succeeds
    r.xadd.return_value = "1-0"
    return r


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """
    Reset module-level singletons before every test so tests are isolated.

    Without this, circuit breaker failures or rate limiter state from one
    test would bleed into the next test.

    lua_scripts._decrement_sha must be set to a truthy value so the Lua
    wrapper does not raise RuntimeError (the lifespan is not run in unit
    tests — ASGITransport does not invoke ASGI lifespan events).
    """
    buy_module._rate_limiter = None
    redis_circuit_breaker._failures = 0
    redis_circuit_breaker._state = State.CLOSED
    redis_circuit_breaker._opened_at = 0.0
    lua_scripts._decrement_sha = "mock-sha"  # prevents RuntimeError in decrement_stock


@pytest.fixture
async def client(mock_redis: AsyncMock) -> AsyncClient:
    """
    httpx AsyncClient pointed at the FastAPI app.

    - Patches init_redis / close_redis so the lifespan doesn't try to
      open a real TCP connection during tests.
    - Overrides get_redis to inject mock_redis into every route.
    """
    app.dependency_overrides[get_redis] = lambda: mock_redis
    with (
        patch("api.main.init_redis", new_callable=AsyncMock),
        patch("api.main.close_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()
