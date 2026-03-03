"""
Tests for EmbeddingService caching behaviour
Phase 6: Caching & Performance Optimization — Step 2
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_service import EmbeddingService

# A realistic-ish embedding vector (shortened to 3 dims for test readability)
_FAKE_VECTOR = [0.1, 0.2, 0.3]
_FAKE_VECTOR_B = [0.4, 0.5, 0.6]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(vectors: list[list[float]]):
    """Build a minimal mock of the OpenAI embeddings response."""
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    response.usage = MagicMock(total_tokens=len(vectors) * 10)
    return response


def _make_service(cache_get_side_effect=None, cache_get_return=None):
    """
    Create an EmbeddingService with:
    - A mock CacheService injected via constructor
    - The OpenAI client replaced by a mock (so no real HTTP calls)
    """
    mock_cache = AsyncMock()
    if cache_get_side_effect is not None:
        mock_cache.get.side_effect = cache_get_side_effect
    else:
        mock_cache.get.return_value = cache_get_return  # None = miss by default
    mock_cache.set = AsyncMock()

    # Patch get_openai_client so __init__ doesn't try to connect
    with patch("app.services.embedding_service.get_openai_client"):
        svc = EmbeddingService(cache=mock_cache)

    # Replace the inner openai client with a mock
    svc.client = MagicMock()
    svc.client.client = MagicMock()
    svc.client.client.embeddings = MagicMock()
    svc.client.client.embeddings.create = AsyncMock()

    return svc, mock_cache


# ---------------------------------------------------------------------------
# generate_embedding — single text
# ---------------------------------------------------------------------------


async def test_generate_embedding_cache_hit():
    """Cache hit → OpenAI is never called."""
    svc, mock_cache = _make_service(cache_get_return=_FAKE_VECTOR)

    result = await svc.generate_embedding("hello")

    assert result == _FAKE_VECTOR
    svc.client.client.embeddings.create.assert_not_awaited()
    print("✓ cache hit skips OpenAI call")


async def test_generate_embedding_cache_miss():
    """Cache miss → OpenAI is called and result is stored in cache."""
    svc, mock_cache = _make_service(cache_get_return=None)
    svc.client.client.embeddings.create.return_value = _make_openai_response(
        [_FAKE_VECTOR]
    )

    result = await svc.generate_embedding("hello")

    assert result == _FAKE_VECTOR
    svc.client.client.embeddings.create.assert_awaited_once()
    mock_cache.set.assert_awaited_once()
    # Verify the cached value is the embedding
    call_args = mock_cache.set.call_args
    assert call_args[0][1] == _FAKE_VECTOR
    print("✓ cache miss calls OpenAI and stores result")


async def test_generate_embedding_cache_returns_none_on_error():
    """
    CacheService.get() swallows Redis errors and returns None internally.
    EmbeddingService treats that None as a cache miss and calls OpenAI.
    """
    # Simulate what the real CacheService does on Redis error: returns None
    svc, mock_cache = _make_service(cache_get_return=None)
    svc.client.client.embeddings.create.return_value = _make_openai_response(
        [_FAKE_VECTOR]
    )

    result = await svc.generate_embedding("hello")

    assert result == _FAKE_VECTOR
    svc.client.client.embeddings.create.assert_awaited_once()
    print("✓ cache None (e.g. after internal Redis error) treated as miss → OpenAI called")


async def test_generate_embedding_cache_key_is_deterministic():
    """Same text always produces the same cache key."""
    svc, _ = _make_service()
    text = "The quick brown fox"
    assert svc._cache_key(text) == svc._cache_key(text)
    print("✓ cache key is deterministic for the same text")


async def test_generate_embedding_different_texts_different_keys():
    """Different texts produce different cache keys."""
    svc, _ = _make_service()
    assert svc._cache_key("text A") != svc._cache_key("text B")
    print("✓ different texts produce different cache keys")


# ---------------------------------------------------------------------------
# generate_embeddings_batch
# ---------------------------------------------------------------------------


async def test_batch_empty_input():
    """Empty list → returns [] immediately, no cache or API calls."""
    svc, mock_cache = _make_service()

    result = await svc.generate_embeddings_batch([])

    assert result == []
    mock_cache.get.assert_not_awaited()
    svc.client.client.embeddings.create.assert_not_awaited()
    print("✓ empty input returns [] without any I/O")


async def test_batch_all_hits():
    """All texts in cache → OpenAI is never called."""
    vectors = [_FAKE_VECTOR, _FAKE_VECTOR_B]
    # Return each vector in order
    mock_cache = AsyncMock()
    mock_cache.get.side_effect = [json.dumps(v) for v in vectors]
    mock_cache.set = AsyncMock()

    with patch("app.services.embedding_service.get_openai_client"):
        svc = EmbeddingService(cache=mock_cache)
    svc.client = MagicMock()
    svc.client.client = MagicMock()
    svc.client.client.embeddings = MagicMock()
    svc.client.client.embeddings.create = AsyncMock()

    # Patch cache.get to deserialize like CacheService does
    mock_cache.get.side_effect = [_FAKE_VECTOR, _FAKE_VECTOR_B]

    result = await svc.generate_embeddings_batch(["text A", "text B"])

    assert result == [_FAKE_VECTOR, _FAKE_VECTOR_B]
    svc.client.client.embeddings.create.assert_not_awaited()
    mock_cache.set.assert_not_awaited()
    print("✓ all cache hits — OpenAI not called")


async def test_batch_all_misses():
    """Nothing cached → OpenAI called for all, all results stored in cache."""
    svc, mock_cache = _make_service(cache_get_return=None)
    svc.client.client.embeddings.create.return_value = _make_openai_response(
        [_FAKE_VECTOR, _FAKE_VECTOR_B]
    )

    result = await svc.generate_embeddings_batch(["text A", "text B"])

    assert result == [_FAKE_VECTOR, _FAKE_VECTOR_B]
    svc.client.client.embeddings.create.assert_awaited_once()
    assert mock_cache.set.await_count == 2
    print("✓ all cache misses — OpenAI called for all, results cached")


async def test_batch_partial_hits_order_preserved():
    """
    Mixed hits/misses: OpenAI called only for misses, results
    merged back into the original order.
    """
    # texts[0] = hit, texts[1] = miss, texts[2] = hit
    hit_miss_hit = [_FAKE_VECTOR, None, _FAKE_VECTOR_B]
    mock_cache = AsyncMock()
    mock_cache.get.side_effect = hit_miss_hit
    mock_cache.set = AsyncMock()

    with patch("app.services.embedding_service.get_openai_client"):
        svc = EmbeddingService(cache=mock_cache)
    svc.client = MagicMock()
    svc.client.client = MagicMock()
    svc.client.client.embeddings = MagicMock()

    miss_vector = [0.7, 0.8, 0.9]
    svc.client.client.embeddings.create = AsyncMock(
        return_value=_make_openai_response([miss_vector])
    )

    result = await svc.generate_embeddings_batch(["A", "B", "C"])

    assert result[0] == _FAKE_VECTOR   # from cache
    assert result[1] == miss_vector    # from OpenAI
    assert result[2] == _FAKE_VECTOR_B  # from cache

    # OpenAI called exactly once (for "B" only)
    svc.client.client.embeddings.create.assert_awaited_once()
    # Only the miss ("B") is written to cache
    assert mock_cache.set.await_count == 1
    call_args = mock_cache.set.call_args
    assert call_args[0][1] == miss_vector
    print("✓ partial hits — order preserved, only misses sent to OpenAI")


async def test_batch_cache_set_uses_embedding_ttl():
    """Embeddings are cached with CACHE_EMBEDDING_TTL."""
    svc, mock_cache = _make_service(cache_get_return=None)
    svc.client.client.embeddings.create.return_value = _make_openai_response(
        [_FAKE_VECTOR]
    )

    with patch("app.services.embedding_service.settings") as mock_settings:
        mock_settings.CACHE_EMBEDDING_TTL = 86400
        await svc.generate_embeddings_batch(["text A"])

    call_args = mock_cache.set.call_args
    assert call_args[1].get("ttl") == 86400 or call_args[0][2] == 86400
    print("✓ embeddings cached with CACHE_EMBEDDING_TTL")


async def test_single_embedding_cache_set_uses_embedding_ttl():
    """generate_embedding stores with CACHE_EMBEDDING_TTL."""
    svc, mock_cache = _make_service(cache_get_return=None)
    svc.client.client.embeddings.create.return_value = _make_openai_response(
        [_FAKE_VECTOR]
    )

    with patch("app.services.embedding_service.settings") as mock_settings:
        mock_settings.CACHE_EMBEDDING_TTL = 86400
        await svc.generate_embedding("some text")

    call_args = mock_cache.set.call_args
    # ttl can be positional or keyword
    ttl = call_args[1].get("ttl") if call_args[1] else call_args[0][2]
    assert ttl == 86400
    print("✓ single embedding cached with CACHE_EMBEDDING_TTL")
