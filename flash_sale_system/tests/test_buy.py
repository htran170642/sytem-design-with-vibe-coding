"""
Tests for POST /buy — the flash sale hot path.

Mocked Redis call sequence for a successful purchase:
  1. eval    → user rate limiter   (1=allowed, 0=rejected)
  2. eval    → global rate limiter (1=allowed, 0=rejected)
  3. set NX  → claim idempotency key (True=claimed, None=duplicate)
  4. evalsha → stock Lua script    (1=ok, 0=sold_out, -1=key missing)
  5. xadd    → enqueue to Redis Stream
  6. set     → resolve idempotency key (pending → order_id)

On duplicate (SET NX returns None):
  - get → "pending"   → status "processing"
  - get → <order_id>  → status "accepted" with the cached order_id
"""

from unittest.mock import AsyncMock

from httpx import AsyncClient

from api.circuit_breaker import State, redis_circuit_breaker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# idempotency_key requires min_length=16
VALID_PAYLOAD = {
    "user_id": "user-1",
    "product_id": "product-1",
    "idempotency_key": "idem-key-1234567890",  # 20 chars ≥ 16
}


def _eval_seq(*values: int) -> list[int]:
    """Rate-limiter eval side_effect; stock uses evalsha (separate mock)."""
    return list(values)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_buy_accepted(client: AsyncClient, mock_redis: AsyncMock) -> None:
    """All checks pass, stock available → accepted."""
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 1

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["order_id"] is not None
    assert "accepted" in data["message"].lower()


async def test_buy_accepted_order_id_is_uuid(client: AsyncClient, mock_redis: AsyncMock) -> None:
    import uuid

    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 1

    response = await client.post("/buy", json=VALID_PAYLOAD)
    uuid.UUID(response.json()["order_id"])  # raises if not valid UUID


async def test_buy_accepted_claims_then_resolves_idempotency(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """
    Two set() calls must happen:
      1. SET NX claim  → (key, "pending", nx=True, ex=...)
      2. Resolve       → (key, order_id, ex=...)
    Key is user-scoped: 'idempotency:<user_id>:<idempotency_key>'
    """
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 1

    response = await client.post("/buy", json=VALID_PAYLOAD)
    order_id = response.json()["order_id"]

    assert mock_redis.set.await_count == 2

    first = mock_redis.set.call_args_list[0]
    assert first[0][0] == "idempotency:user-1:idem-key-1234567890"
    assert first[0][1] == "pending"
    assert first[1].get("nx") is True

    second = mock_redis.set.call_args_list[1]
    assert second[0][0] == "idempotency:user-1:idem-key-1234567890"
    assert second[0][1] == order_id
    assert "nx" not in second[1]


async def test_buy_accepted_enqueues_to_stream(client: AsyncClient, mock_redis: AsyncMock) -> None:
    """Order must be pushed to the Redis stream before returning."""
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 1

    response = await client.post("/buy", json=VALID_PAYLOAD)
    order_id = response.json()["order_id"]

    mock_redis.xadd.assert_awaited_once()
    stream = mock_redis.xadd.call_args[0][0]
    payload = mock_redis.xadd.call_args[0][1]

    assert stream == "orders"
    assert payload["order_id"] == order_id
    assert payload["user_id"] == "user-1"
    assert payload["product_id"] == "product-1"


# ---------------------------------------------------------------------------
# Idempotency — duplicate request
# ---------------------------------------------------------------------------


async def test_buy_duplicate_returns_accepted_with_cached_order_id(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """
    SET NX fails (key exists) + GET returns a resolved order_id
    → returns 'accepted' with the cached order_id.
    """
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.set.return_value = None  # claim fails
    mock_redis.get.return_value = "cached-order-id-abcdef"  # resolved

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["order_id"] == "cached-order-id-abcdef"


async def test_buy_duplicate_in_flight_returns_processing(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """
    SET NX fails + GET returns 'pending' (first request still in-flight)
    → returns 'processing'.
    """
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.set.return_value = None
    mock_redis.get.return_value = "pending"

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


async def test_buy_duplicate_does_not_decrement_stock(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """evalsha (stock) must NOT be called on a duplicate request."""
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.set.return_value = None
    mock_redis.get.return_value = "cached-order-id-abcdef"

    await client.post("/buy", json=VALID_PAYLOAD)

    mock_redis.evalsha.assert_not_awaited()


async def test_buy_duplicate_does_not_enqueue(client: AsyncClient, mock_redis: AsyncMock) -> None:
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.set.return_value = None
    mock_redis.get.return_value = "cached-order-id-abcdef"

    await client.post("/buy", json=VALID_PAYLOAD)

    mock_redis.xadd.assert_not_awaited()


# ---------------------------------------------------------------------------
# Stock sold out
# ---------------------------------------------------------------------------


async def test_buy_sold_out(client: AsyncClient, mock_redis: AsyncMock) -> None:
    """evalsha returns 0 → sold_out response."""
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 0

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sold_out"
    assert data["order_id"] is None


async def test_buy_sold_out_does_not_enqueue(client: AsyncClient, mock_redis: AsyncMock) -> None:
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 0

    await client.post("/buy", json=VALID_PAYLOAD)

    mock_redis.xadd.assert_not_awaited()


async def test_buy_sold_out_releases_idempotency_key(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """
    On sold_out the claimed key is deleted so the caller can retry
    with the same idempotency key.
    """
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 0

    await client.post("/buy", json=VALID_PAYLOAD)

    mock_redis.delete.assert_awaited_once_with("idempotency:user-1:idem-key-1234567890")


async def test_buy_product_key_missing_treated_as_sold_out(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """evalsha returns -1 (key not preloaded) → treated as sold_out."""
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = -1

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["status"] == "sold_out"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def test_buy_user_rate_limited(client: AsyncClient, mock_redis: AsyncMock) -> None:
    """Per-user eval returns 0 → 429."""
    mock_redis.eval.return_value = 0

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


async def test_buy_global_rate_limited(client: AsyncClient, mock_redis: AsyncMock) -> None:
    """User OK, global rejected → 429."""
    mock_redis.eval.side_effect = _eval_seq(1, 0)

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 429
    assert "capacity" in response.json()["detail"]


async def test_buy_rate_limited_does_not_touch_stock(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """When rate limited, evalsha (stock) must never be called."""
    mock_redis.eval.return_value = 0

    await client.post("/buy", json=VALID_PAYLOAD)

    mock_redis.evalsha.assert_not_awaited()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


async def test_buy_circuit_breaker_open_returns_503(
    client: AsyncClient,
) -> None:
    """If circuit is open, return 503 immediately."""
    redis_circuit_breaker._state = State.OPEN
    redis_circuit_breaker._opened_at = float("inf")

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 503


async def test_buy_redis_error_increments_failure_count(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """Unexpected Redis exception → circuit breaker records a failure."""
    mock_redis.eval.side_effect = ConnectionError("Redis is down")

    response = await client.post("/buy", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert redis_circuit_breaker._failures == 1


async def test_buy_redis_errors_trip_circuit_breaker(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """After threshold consecutive failures, circuit opens."""
    mock_redis.eval.side_effect = ConnectionError("Redis is down")

    for _ in range(5):
        await client.post("/buy", json=VALID_PAYLOAD)

    assert redis_circuit_breaker.state is State.OPEN


async def test_buy_429_does_not_trip_circuit_breaker(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """HTTP 429 is intentional — must not count as a circuit breaker failure."""
    mock_redis.eval.return_value = 0

    for _ in range(10):
        await client.post("/buy", json=VALID_PAYLOAD)

    assert redis_circuit_breaker._failures == 0
    assert redis_circuit_breaker.state is State.CLOSED


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


async def test_buy_missing_user_id_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/buy",
        json={"product_id": "p1", "idempotency_key": "a" * 16},
    )
    assert response.status_code == 422


async def test_buy_missing_product_id_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/buy",
        json={"user_id": "u1", "idempotency_key": "a" * 16},
    )
    assert response.status_code == 422


async def test_buy_missing_idempotency_key_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/buy",
        json={"user_id": "u1", "product_id": "p1"},
    )
    assert response.status_code == 422


async def test_buy_empty_string_user_id_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/buy",
        json={"user_id": "", "product_id": "p1", "idempotency_key": "a" * 16},
    )
    assert response.status_code == 422


async def test_buy_idempotency_key_too_short_returns_422(client: AsyncClient) -> None:
    """idempotency_key requires min_length=16."""
    response = await client.post(
        "/buy",
        json={"user_id": "u1", "product_id": "p1", "idempotency_key": "short"},
    )
    assert response.status_code == 422


async def test_buy_wrong_content_type_returns_422(client: AsyncClient) -> None:
    response = await client.post("/buy", content="not-json")
    assert response.status_code in (422, 400)


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_buy_response_has_required_fields(client: AsyncClient, mock_redis: AsyncMock) -> None:
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 1

    response = await client.post("/buy", json=VALID_PAYLOAD)
    data = response.json()

    assert "status" in data
    assert "message" in data
    assert "order_id" in data


async def test_buy_sold_out_response_has_no_order_id(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    mock_redis.eval.side_effect = _eval_seq(1, 1)
    mock_redis.evalsha.return_value = 0

    response = await client.post("/buy", json=VALID_PAYLOAD)
    assert response.json()["order_id"] is None
