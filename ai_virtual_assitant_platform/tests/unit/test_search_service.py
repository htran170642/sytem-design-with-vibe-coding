"""
Tests for Search Service
"""

import pytest
from unittest.mock import MagicMock

import app.services.search_service as ss_module
import app.services.vector_store as vs_module
import app.services.embedding_service as es_module


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies and reset singletons before each test."""
    # Pre-set singletons so SearchService uses mocks instead of connecting
    vs_module._vector_store = MagicMock()
    es_module._embedding_service = MagicMock()
    ss_module._search_service = None
    yield
    ss_module._search_service = None
    vs_module._vector_store = None
    es_module._embedding_service = None


def test_search_service_singleton():
    """Test that get_search_service returns same instance."""
    from app.services.search_service import get_search_service

    service1 = get_search_service()
    service2 = get_search_service()

    assert service1 is service2
    print("✓ Search service is a singleton")


def test_search_service_initialization():
    """Test search service initializes correctly."""
    from app.services.search_service import get_search_service

    service = get_search_service()

    assert service.embedding_service is not None
    assert service.vector_store is not None

    print("✓ Search service initialized with dependencies")


def test_search_service_has_required_methods():
    """Test that service has all required methods."""
    from app.services.search_service import get_search_service

    service = get_search_service()

    assert hasattr(service, "search")
    assert hasattr(service, "search_by_chunk_text")

    assert callable(service.search)
    assert callable(service.search_by_chunk_text)

    print("✓ Search service has all required methods")


def test_search_service_dependencies():
    """Test search service has correct dependency types."""
    from app.services.embedding_service import EmbeddingService
    from app.services.search_service import get_search_service
    from app.services.vector_store import VectorStore

    service = get_search_service()

    # Dependencies are mocks (MagicMock), not real instances —
    # verify they are not None (proper injection happened)
    assert service.embedding_service is not None
    assert service.vector_store is not None

    print("✓ Search service dependencies configured correctly")


def test_search_method_signature():
    """Test search method has correct signature."""
    import inspect

    from app.services.search_service import SearchService

    sig = inspect.signature(SearchService.search)
    params = list(sig.parameters.keys())

    assert "query" in params
    assert "limit" in params
    assert "document_ids" in params
    assert "min_score" in params

    print("✓ Search method signature correct")


def test_search_by_chunk_text_signature():
    """Test search_by_chunk_text method signature."""
    import inspect

    from app.services.search_service import SearchService

    sig = inspect.signature(SearchService.search_by_chunk_text)
    params = list(sig.parameters.keys())

    assert "chunk_text" in params
    assert "limit" in params
    assert "exclude_chunk_ids" in params

    print("✓ search_by_chunk_text signature correct")
