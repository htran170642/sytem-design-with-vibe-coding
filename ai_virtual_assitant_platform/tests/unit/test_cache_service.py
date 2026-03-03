"""
Tests for Cache Service
Phase 6: Caching & Performance Optimization — Step 1
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache_service import CacheService, CacheStats, get_cache_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service_with_mock_redis(return_value=None, side_effect=None):
    """Create a CacheService whose internal Redis client is fully mocked."""
    service = CacheService.__new__(CacheService)
    service._hits = 0
    service._misses = 0

    mock_redis = AsyncMock()

    # Default: GET returns None (miss)
    if side_effect is not None:
        mock_redis.get.side_effect = side_effect
    else:
        mock_redis.get.return_value = return_value

    mock_redis.setex = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)

    service._redis = mock_redis
    return service, mock_redis


# ---------------------------------------------------------------------------
# CacheStats
# ---------------------------------------------------------------------------


def test_cache_stats_hit_rate_zero_when_no_calls():
    stats = CacheStats(hits=0, misses=0)
    assert stats.hit_rate == 0.0
    print("✓ hit_rate is 0.0 when no calls")


def test_cache_stats_hit_rate_calculation():
    stats = CacheStats(hits=3, misses=1)
    assert stats.hit_rate == pytest.approx(0.75)
    print("✓ hit_rate calculated correctly")


def test_cache_stats_repr_contains_hit_rate():
    stats = CacheStats(hits=1, misses=1)
    assert "50.0%" in repr(stats)
    print("✓ repr contains formatted hit_rate")


# ---------------------------------------------------------------------------
# Key builders (sync — no Redis needed)
# ---------------------------------------------------------------------------


def test_make_key_format():
    key = CacheService.make_key("ai_response", "gpt-4o", "req-abc")
    assert key == "aiva:ai_response:gpt-4o:req-abc"
    print("✓ make_key produces correct format")


def test_make_key_single_part():
    key = CacheService.make_key("faq", "42")
    assert key == "aiva:faq:42"
    print("✓ make_key works with single part")


def test_hash_key_format():
    key = CacheService.hash_key("embedding", "hello world")
    # Should start with prefix and namespace
    assert key.startswith("aiva:embedding:")
    # Hash suffix should be exactly 16 hex chars
    suffix = key.split(":")[-1]
    assert len(suffix) == 16
    assert all(c in "0123456789abcdef" for c in suffix)
    print("✓ hash_key format is correct")


def test_hash_key_deterministic():
    text = "The quick brown fox"
    k1 = CacheService.hash_key("embedding", text)
    k2 = CacheService.hash_key("embedding", text)
    assert k1 == k2
    print("✓ hash_key is deterministic")


def test_hash_key_different_texts_produce_different_keys():
    k1 = CacheService.hash_key("embedding", "text A")
    k2 = CacheService.hash_key("embedding", "text B")
    assert k1 != k2
    print("✓ hash_key produces different keys for different texts")


# ---------------------------------------------------------------------------
# get() — miss
# ---------------------------------------------------------------------------


async def test_get_returns_none_on_miss():
    service, mock_redis = _make_service_with_mock_redis(return_value=None)

    result = await service.get("aiva:test:key")

    assert result is None
    assert service._misses == 1
    assert service._hits == 0
    print("✓ get returns None on cache miss and increments miss counter")


async def test_get_increments_miss_counter():
    service, _ = _make_service_with_mock_redis(return_value=None)

    await service.get("key1")
    await service.get("key2")

    assert service._misses == 2
    print("✓ miss counter accumulates")


# ---------------------------------------------------------------------------
# get() — hit
# ---------------------------------------------------------------------------


async def test_get_returns_deserialized_value_on_hit():
    payload = {"answer": "42", "confidence": 0.9}
    service, mock_redis = _make_service_with_mock_redis(
        return_value=json.dumps(payload)
    )

    result = await service.get("aiva:test:key")

    assert result == payload
    assert service._hits == 1
    assert service._misses == 0
    print("✓ get returns deserialized value on cache hit")


async def test_get_hit_works_with_list_value():
    value = [0.1, 0.2, 0.3]
    service, _ = _make_service_with_mock_redis(return_value=json.dumps(value))

    result = await service.get("aiva:embedding:abc")

    assert result == value
    assert service._hits == 1
    print("✓ get handles list values (e.g. embedding vectors)")


async def test_get_treats_invalid_json_as_miss():
    service, _ = _make_service_with_mock_redis(return_value="not-valid-json{{{")

    result = await service.get("aiva:bad:key")

    assert result is None
    assert service._misses == 1
    print("✓ get treats non-JSON stored value as a miss")


# ---------------------------------------------------------------------------
# get() — disabled
# ---------------------------------------------------------------------------


async def test_get_returns_none_when_cache_disabled():
    service, mock_redis = _make_service_with_mock_redis(
        return_value=json.dumps({"answer": "cached"})
    )

    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.CACHE_ENABLED = False
        mock_settings.CACHE_DEFAULT_TTL = 600

        result = await service.get("aiva:test:key")

    assert result is None
    mock_redis.get.assert_not_called()
    print("✓ get skips Redis entirely when CACHE_ENABLED=False")


# ---------------------------------------------------------------------------
# get() — Redis error
# ---------------------------------------------------------------------------


async def test_get_returns_none_on_redis_error():
    service, _ = _make_service_with_mock_redis(side_effect=Exception("conn refused"))

    result = await service.get("aiva:test:key")

    assert result is None
    assert service._misses == 1
    print("✓ get gracefully returns None on Redis connection error")


# ---------------------------------------------------------------------------
# set()
# ---------------------------------------------------------------------------


async def test_set_calls_setex_with_provided_ttl():
    service, mock_redis = _make_service_with_mock_redis()

    await service.set("aiva:test:key", {"data": 1}, ttl=120)

    mock_redis.setex.assert_awaited_once_with("aiva:test:key", 120, json.dumps({"data": 1}))
    print("✓ set calls setex with the correct TTL")


async def test_set_uses_default_ttl_when_none():
    service, mock_redis = _make_service_with_mock_redis()

    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.CACHE_ENABLED = True
        mock_settings.CACHE_DEFAULT_TTL = 600

        await service.set("aiva:test:key", "hello")

    mock_redis.setex.assert_awaited_once_with("aiva:test:key", 600, json.dumps("hello"))
    print("✓ set uses CACHE_DEFAULT_TTL when ttl=None")


async def test_set_calls_plain_set_when_ttl_is_zero():
    service, mock_redis = _make_service_with_mock_redis()

    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.CACHE_ENABLED = True
        mock_settings.CACHE_DEFAULT_TTL = 600

        await service.set("aiva:test:key", "persist", ttl=0)

    mock_redis.set.assert_awaited_once()
    mock_redis.setex.assert_not_awaited()
    print("✓ set uses plain SET (no expiry) when ttl=0")


async def test_set_skips_redis_when_cache_disabled():
    service, mock_redis = _make_service_with_mock_redis()

    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.CACHE_ENABLED = False
        mock_settings.CACHE_DEFAULT_TTL = 600

        await service.set("aiva:test:key", {"x": 1})

    mock_redis.setex.assert_not_awaited()
    mock_redis.set.assert_not_awaited()
    print("✓ set is a no-op when CACHE_ENABLED=False")


async def test_set_skips_on_non_serializable_value():
    service, mock_redis = _make_service_with_mock_redis()

    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.CACHE_ENABLED = True
        mock_settings.CACHE_DEFAULT_TTL = 600

        # A set() object is not JSON-serializable
        await service.set("aiva:test:key", {1, 2, 3})

    mock_redis.setex.assert_not_awaited()
    print("✓ set skips silently when value is not JSON-serializable")


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


async def test_delete_calls_redis_delete():
    service, mock_redis = _make_service_with_mock_redis()

    await service.delete("aiva:test:key")

    mock_redis.delete.assert_awaited_once_with("aiva:test:key")
    print("✓ delete calls redis.delete with correct key")


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------


async def test_exists_returns_true_when_key_present():
    service, mock_redis = _make_service_with_mock_redis()
    mock_redis.exists.return_value = 1

    result = await service.exists("aiva:test:key")

    assert result is True
    print("✓ exists returns True when Redis reports key present")


async def test_exists_returns_false_when_key_absent():
    service, mock_redis = _make_service_with_mock_redis()
    mock_redis.exists.return_value = 0

    result = await service.exists("aiva:test:key")

    assert result is False
    print("✓ exists returns False when Redis reports key absent")


# ---------------------------------------------------------------------------
# get_stats() / reset_stats()
# ---------------------------------------------------------------------------


async def test_get_stats_returns_correct_counts():
    service, mock_redis = _make_service_with_mock_redis(return_value=None)
    # Miss
    await service.get("miss1")
    # Hit
    mock_redis.get.return_value = json.dumps("cached")
    await service.get("hit1")

    stats = service.get_stats()

    assert isinstance(stats, CacheStats)
    assert stats.misses == 1
    assert stats.hits == 1
    assert stats.hit_rate == pytest.approx(0.5)
    print("✓ get_stats returns correct hit/miss counts")


def test_reset_stats_zeroes_counters():
    service, _ = _make_service_with_mock_redis()
    service._hits = 10
    service._misses = 5

    service.reset_stats()

    stats = service.get_stats()
    assert stats.hits == 0
    assert stats.misses == 0
    print("✓ reset_stats zeroes all counters")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_cache_service_returns_singleton():
    # Reset singleton before test
    import app.services.cache_service as cache_module

    cache_module._cache_service = None

    s1 = get_cache_service()
    s2 = get_cache_service()

    assert s1 is s2
    print("✓ get_cache_service returns same instance (singleton)")
