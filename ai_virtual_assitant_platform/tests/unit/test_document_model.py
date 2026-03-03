"""
Tests for Document ORM model and related utilities
Phase 7: Database & Persistence
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse


# ---------------------------------------------------------------------------
# DocumentStatus enum
# ---------------------------------------------------------------------------


def test_document_status_values():
    """All expected status values are present and are strings."""
    assert DocumentStatus.PENDING == "pending"
    assert DocumentStatus.PROCESSING == "processing"
    assert DocumentStatus.COMPLETED == "completed"
    assert DocumentStatus.FAILED == "failed"


def test_document_status_is_str_enum():
    """DocumentStatus can be compared directly with plain strings."""
    assert DocumentStatus.PENDING == "pending"
    assert "completed" == DocumentStatus.COMPLETED


# ---------------------------------------------------------------------------
# Document model instantiation
# ---------------------------------------------------------------------------


def _make_doc(**overrides) -> Document:
    defaults = dict(
        public_id="550e8400-e29b-41d4-a716-446655440000",
        filename="report.pdf",
        original_filename="report.pdf",
        file_path="/uploads/550e/report.pdf",
        file_type="pdf",
        file_size=1024 * 512,
        status=DocumentStatus.PENDING,
        qdrant_collection="aiva_documents_dev",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    # Use the proper SQLAlchemy constructor so instrumented attributes work
    doc = Document(**defaults)
    return doc


def test_document_model_repr():
    doc = _make_doc()
    assert "report.pdf" in repr(doc)
    assert "pending" in repr(doc)


def test_document_optional_fields_default_none():
    doc = _make_doc()
    assert doc.chunk_count is None
    assert doc.embedding_model is None
    assert doc.doc_metadata is None
    assert doc.error_message is None


def test_document_with_all_fields():
    doc = _make_doc(
        status=DocumentStatus.COMPLETED,
        chunk_count=42,
        embedding_model="text-embedding-3-small",
        doc_metadata={"pages": 5, "author": "Jane"},
    )
    assert doc.chunk_count == 42
    assert doc.embedding_model == "text-embedding-3-small"
    assert doc.doc_metadata["pages"] == 5


# ---------------------------------------------------------------------------
# Schema conversion (from_attributes)
# ---------------------------------------------------------------------------


def test_document_response_from_orm_object():
    """DocumentResponse.model_validate() correctly converts a Document ORM object."""
    doc = _make_doc(
        id=7,
        filename="guide.pdf",
        file_type="pdf",
        file_size=2048,
        status=DocumentStatus.COMPLETED,
        chunk_count=10,
        embedding_model="text-embedding-3-small",
    )

    response = DocumentResponse.model_validate(doc)

    assert response.id == 7
    assert response.filename == "guide.pdf"
    assert response.file_type == "pdf"
    assert response.file_size == 2048
    assert response.status == "completed"
    assert response.chunk_count == 10
    assert response.embedding_model == "text-embedding-3-small"


def test_document_response_from_orm_pending_doc():
    """Schema works for a freshly-uploaded (pending) document with nulls."""
    doc = _make_doc(id=2, status=DocumentStatus.PENDING)
    response = DocumentResponse.model_validate(doc)

    assert response.status == "pending"
    assert response.embedding_model is None


# ---------------------------------------------------------------------------
# _update_db_status helper
# ---------------------------------------------------------------------------


def _mock_session_factory(mock_doc):
    """Build a mock AsyncSessionLocal that yields mock_doc from session.get()."""
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_doc
    mock_session.commit = AsyncMock()

    # AsyncSessionLocal() must work as an async context manager
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_factory, mock_session


@pytest.mark.asyncio
async def test_update_db_status_updates_fields():
    """_update_db_status should set status and optional fields on the Document."""
    from app.tasks.document_tasks import _update_db_status

    mock_doc = _make_doc(status=DocumentStatus.PENDING)
    mock_factory, mock_session = _mock_session_factory(mock_doc)

    with patch("app.tasks.document_tasks.AsyncSessionLocal", mock_factory):
        await _update_db_status(
            1,
            DocumentStatus.COMPLETED,
            chunk_count=20,
            embedding_model="text-embedding-3-small",
        )

    assert mock_doc.status == DocumentStatus.COMPLETED
    assert mock_doc.chunk_count == 20
    assert mock_doc.embedding_model == "text-embedding-3-small"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_db_status_handles_missing_document():
    """_update_db_status should not crash if the document doesn't exist in DB."""
    from app.tasks.document_tasks import _update_db_status

    mock_factory, mock_session = _mock_session_factory(mock_doc=None)

    with patch("app.tasks.document_tasks.AsyncSessionLocal", mock_factory):
        # Should not raise
        await _update_db_status(999, DocumentStatus.FAILED, error_message="boom")

    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_db_status_sets_error_message():
    """_update_db_status with status=failed should persist the error_message."""
    from app.tasks.document_tasks import _update_db_status

    mock_doc = _make_doc(status=DocumentStatus.PROCESSING)
    mock_factory, mock_session = _mock_session_factory(mock_doc)

    with patch("app.tasks.document_tasks.AsyncSessionLocal", mock_factory):
        await _update_db_status(1, DocumentStatus.FAILED, error_message="Qdrant timeout")

    assert mock_doc.status == DocumentStatus.FAILED
    assert mock_doc.error_message == "Qdrant timeout"
