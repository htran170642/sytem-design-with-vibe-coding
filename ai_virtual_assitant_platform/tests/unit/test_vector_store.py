"""
Tests for Vector Store Service
"""

import pytest
from unittest.mock import MagicMock, patch

import app.services.vector_store as vs_module


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset vector store singleton before each test."""
    original = vs_module._vector_store
    vs_module._vector_store = None
    yield
    vs_module._vector_store = original


@pytest.fixture(autouse=True)
def mock_qdrant_client():
    """Mock QdrantClient to avoid real Qdrant connections."""
    with patch("app.services.vector_store.QdrantClient") as mock_cls:
        client = MagicMock()

        # _ensure_collection_exists calls get_collections()
        mock_collection = MagicMock()
        mock_collection.name = "aiva_documents_dev"
        client.get_collections.return_value = MagicMock(collections=[mock_collection])

        # get_collection_info calls count()
        count_result = MagicMock()
        count_result.count = 42
        client.count.return_value = count_result

        mock_cls.return_value = client
        yield client


def test_vector_store_singleton():
    """Test that get_vector_store returns same instance."""
    from app.services.vector_store import get_vector_store

    store1 = get_vector_store()
    store2 = get_vector_store()

    assert store1 is store2
    print("✓ Vector store is a singleton")


def test_vector_store_initialization():
    """Test vector store initializes correctly."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    assert store.collection_name == "aiva_documents_dev"
    assert store.vector_size == 1536
    assert store.client is not None

    print("✓ Vector store initialized with correct settings")


def test_vector_store_has_required_methods():
    """Test that store has all required methods."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    assert hasattr(store, "upsert_embeddings")
    assert hasattr(store, "search")
    assert hasattr(store, "delete_by_document_id")
    assert hasattr(store, "get_collection_info")

    assert callable(store.upsert_embeddings)
    assert callable(store.search)
    assert callable(store.delete_by_document_id)
    assert callable(store.get_collection_info)

    print("✓ Vector store has all required methods")


def test_collection_name():
    """Test correct collection name."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    assert store.collection_name == "aiva_documents_dev"
    print("✓ Collection name correct (aiva_documents_dev)")


def test_vector_dimensions():
    """Test vector dimensions match expected size."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    assert store.vector_size == 1536
    print("✓ Vector dimensions correct (1536)")


def test_distance_metric():
    """Test using cosine similarity."""
    from qdrant_client.models import Distance

    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    assert store.distance == Distance.COSINE
    print("✓ Using cosine similarity for vector comparison")


def test_collection_creation():
    """Test that collection lookup is called during initialization."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    # The mocked client's get_collections was called during __init__
    store.client.get_collections.assert_called()
    print("✓ Collection existence check called during init")


def test_get_collection_info():
    """Test getting collection statistics."""
    from app.services.vector_store import get_vector_store

    store = get_vector_store()

    info = store.get_collection_info()

    assert "vector_count" in info
    assert "vector_size" in info
    assert info["vector_size"] == 1536

    print("✓ Collection info retrieval works")
    print(f"  - Vector count: {info.get('vector_count', 0)}")
    print(f"  - Vector size: {info.get('vector_size', 0)}")
