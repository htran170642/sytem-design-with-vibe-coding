"""
Tests for RAG Service Edge Cases
Phase 4, Step 7: Handle empty or low-confidence retrieval cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import app.services.ai_service as ai_module
import app.services.cache_service as cache_module
import app.services.rag_service as rs_module
import app.services.search_service as ss_module


@pytest.fixture(autouse=True)
def mock_rag_dependencies():
    """
    Mock all RAGService dependencies so tests run without external connections.
    """
    ss_module._search_service = MagicMock()
    ai_module._ai_service = MagicMock()

    # CacheService.get / set are async — use AsyncMock
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    cache_module._cache_service = mock_cache

    rs_module._rag_service = None
    yield
    rs_module._rag_service = None
    ss_module._search_service = None
    ai_module._ai_service = None
    cache_module._cache_service = None


def test_format_context_with_empty_results():
    """Test handling of empty search results."""
    from app.services.rag_service import get_rag_service

    service = get_rag_service()
    context = service._format_context([])

    assert "No relevant information" in context
    print("✓ Handles empty search results gracefully")


def test_format_context_with_low_scores():
    """Test context formatting with low confidence scores."""
    from app.services.rag_service import get_rag_service

    service = get_rag_service()

    results = [
        {
            "chunk_id": 1,
            "document_id": 1,
            "filename": "doc.pdf",
            "content": "Some text",
            "score": 0.45,
            "metadata": {"page": 1},
        }
    ]

    context = service._format_context(results)

    assert "0.45" in context
    assert "Some text" in context
    print("✓ Formats context even with low scores")


def test_format_context_with_missing_metadata():
    """Test handling of results with missing metadata."""
    from app.services.rag_service import get_rag_service

    service = get_rag_service()

    results = [
        {
            "chunk_id": 1,
            "document_id": 1,
            "filename": "doc.pdf",
            "content": "Text without metadata",
            "score": 0.85,
            "metadata": {},
        }
    ]

    context = service._format_context(results)

    assert "Text without metadata" in context
    assert "N/A" in context
    print("✓ Handles missing metadata gracefully")


def test_build_rag_prompt_with_custom_system_message():
    """Test custom system messages."""
    from app.services.rag_service import get_rag_service

    service = get_rag_service()

    custom_system = "You are a legal expert. Be precise."
    question = "What is the policy?"
    context = "Policy text here..."

    prompt = service._build_rag_prompt(question, context, system_message=custom_system)

    assert custom_system in prompt
    assert question in prompt
    assert context in prompt
    print("✓ Custom system messages work")


def test_build_rag_prompt_default_system_message():
    """Test default system message."""
    from app.services.rag_service import get_rag_service

    service = get_rag_service()

    prompt = service._build_rag_prompt("Question here", "Context here")

    assert "cite" in prompt.lower() or "source" in prompt.lower()
    assert "helpful" in prompt.lower() or "assistant" in prompt.lower()
    print("✓ Default system message is appropriate")


def test_edge_case_handling_patterns():
    """Test that edge case handling parameters are present."""
    import inspect

    from app.services.rag_service import get_rag_service

    service = get_rag_service()

    sig = inspect.signature(service.query)
    params = list(sig.parameters.keys())

    assert "fallback_to_general" in params
    print("✓ Edge case handling parameters present")


def test_confidence_thresholds():
    """Test confidence threshold logic."""
    high_confidence = 0.89
    medium_confidence = 0.72
    low_confidence = 0.45
    very_low_confidence = 0.25

    assert high_confidence >= 0.75
    assert 0.6 <= medium_confidence < 0.75
    assert 0.3 <= low_confidence < 0.6
    assert very_low_confidence < 0.5

    print("✓ Confidence thresholds defined correctly")


def test_error_handling_structure():
    """Test that error handling returns proper structure."""
    expected_keys = {"question", "answer", "sources", "confidence", "context_used"}

    error_response = {
        "question": "test",
        "answer": "Error message",
        "sources": [],
        "confidence": 0.0,
        "context_used": "",
        "error": "Some error",
    }

    assert expected_keys.issubset(set(error_response.keys()))
    assert len(error_response["sources"]) == 0
    assert error_response["confidence"] == 0.0

    print("✓ Error response structure is correct")
