"""
Tests for GET /health.
"""

from unittest.mock import AsyncMock

from httpx import AsyncClient


async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_redis_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["redis"] == "ok"


async def test_health_redis_down_still_returns_200(
    client: AsyncClient, mock_redis: AsyncMock
) -> None:
    """
    Health check must not crash when Redis is unreachable.
    The overall status is still 'ok' (the API is up) but redis is 'unavailable'.
    """
    mock_redis.ping.side_effect = ConnectionError("Redis unreachable")

    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["redis"] == "unavailable"
