"""
Tests for RAG response caching
Phase 6, Step 3: Cache AI responses for idempotent requests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache_service import CacheService
from app.services.rag_service import RAGService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_ANSWER = "Based on the documents, the answer is X [Source 1]."

_FAKE_SEARCH_RESULT = {
    "chunk_id": 1,
    "document_id": 1,
    "filename": "doc.pdf",
    "content": "The answer is X.",
    "score": 0.85,
    "metadata": {"page": 1},
}


def _make_rag_service(*, cache_get_return=None, search_return=None, ai_answer=_FAKE_ANSWER):
    """
    Build a RAGService with fully mocked dependencies.
    All external calls (Redis, OpenAI, Qdrant) are stubbed out.
    """
    mock_cache = AsyncMock()
    mock_cache.get.return_value = cache_get_return  # None = miss by default
    mock_cache.set = AsyncMock()

    mock_search = AsyncMock()
    mock_search.search.return_value = search_return if search_return is not None else [_FAKE_SEARCH_RESULT]

    mock_ai = AsyncMock()
    mock_ai.simple_chat.return_value = ai_answer
    mock_ai.chat_completion.return_value = {"message": ai_answer}

    with (
        patch("app.services.rag_service.get_cache_service", return_value=mock_cache),
        patch("app.services.rag_service.get_search_service", return_value=mock_search),
        patch("app.services.rag_service.get_ai_service", return_value=mock_ai),
    ):
        svc = RAGService()

    return svc, mock_cache, mock_search, mock_ai


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result_immediately():
    """A warm cache must skip search and LLM entirely and return the cached dict."""
    cached_response = {
        "question": "What is X?",
        "answer": _FAKE_ANSWER,
        "sources": [_FAKE_SEARCH_RESULT],
        "confidence": 0.85,
        "context_used": "some context",
    }
    svc, mock_cache, mock_search, mock_ai = _make_rag_service(cache_get_return=cached_response)

    result = await svc.query("What is X?")

    # Should return cached value with cached=True flag
    assert result["answer"] == _FAKE_ANSWER
    assert result["cached"] is True

    # No expensive operations should have been called
    mock_search.search.assert_not_called()
    mock_ai.simple_chat.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_does_not_call_cache_set():
    """When the cache is warm we must not write back to it."""
    cached_response = {"question": "Q", "answer": "A", "sources": [], "confidence": 0.9}
    svc, mock_cache, _, _ = _make_rag_service(cache_get_return=cached_response)

    await svc.query("Q")

    mock_cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# Cache miss — successful RAG
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_runs_full_pipeline():
    """On a cold cache the full search→LLM pipeline must execute."""
    svc, mock_cache, mock_search, mock_ai = _make_rag_service()

    result = await svc.query("What is X?")

    assert result["answer"] == _FAKE_ANSWER
    mock_search.search.assert_called_once()
    mock_ai.simple_chat.assert_called_once()


@pytest.mark.asyncio
async def test_cache_miss_stores_successful_result():
    """After a successful RAG response the result must be written to cache."""
    svc, mock_cache, _, _ = _make_rag_service()

    await svc.query("What is X?")

    mock_cache.set.assert_called_once()
    # Verify TTL kwarg was passed
    _, kwargs = mock_cache.set.call_args
    assert "ttl" in kwargs


@pytest.mark.asyncio
async def test_cache_key_covers_query_parameters():
    """Different question values must produce different cache keys."""
    key_a = CacheService.hash_key("ai_response", f"question A:{[]}:5:0.3:False")
    key_b = CacheService.hash_key("ai_response", f"question B:{[]}:5:0.3:False")
    assert key_a != key_b


@pytest.mark.asyncio
async def test_same_params_produce_same_cache_key():
    """Identical inputs must always hash to the same key (determinism)."""
    q = "What is the refund policy?"
    params = f"{q}:{sorted([])}:5:0.3:False"
    key_1 = CacheService.hash_key("ai_response", params)
    key_2 = CacheService.hash_key("ai_response", params)
    assert key_1 == key_2


# ---------------------------------------------------------------------------
# No-result path — must NOT be cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_results_no_fallback_is_not_cached():
    """
    When search returns nothing and fallback_to_general=False, the 'no documents'
    response should NOT be cached (documents may be uploaded later).
    """
    svc, mock_cache, _, _ = _make_rag_service(search_return=[])

    result = await svc.query("What is X?", fallback_to_general=False)

    assert result["confidence"] == 0.0
    assert "sources" in result
    mock_cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# Fallback to general knowledge — must be cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_to_general_result_is_cached():
    """When falling back to general LLM knowledge the result must be cached."""
    svc, mock_cache, _, mock_ai = _make_rag_service(search_return=[])
    mock_ai.simple_chat.return_value = "General knowledge answer."

    result = await svc.query("What is X?", fallback_to_general=True)

    assert result["fallback_used"] is True
    mock_cache.set.assert_called_once()


# ---------------------------------------------------------------------------
# Error path — must NOT be cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_result_is_not_cached():
    """Errors from the pipeline must not be persisted to cache."""
    svc, mock_cache, mock_search, _ = _make_rag_service()
    mock_search.search.side_effect = RuntimeError("Qdrant unavailable")

    result = await svc.query("What is X?")

    assert "error" in result
    mock_cache.set.assert_not_called()
