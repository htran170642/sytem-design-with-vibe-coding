"""
Integration tests for API endpoints.
Phase 8, Step 4: Write integration tests for API endpoints.

Uses httpx.AsyncClient with the real FastAPI app (full middleware stack).
External dependencies (DB, Qdrant, Celery, OpenAI) are mocked via
FastAPI dependency overrides or unittest.mock.patch.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db import get_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_KEY = "878f56e6e56726153aa865aed057b5e9"
AUTH = {"X-API-Key": API_KEY}
BASE = "http://test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db_session(**kwargs) -> AsyncMock:
    """Return an AsyncMock that looks like an AsyncSession."""
    session = AsyncMock()
    for attr, val in kwargs.items():
        setattr(session, attr, val)
    return session


@pytest.fixture()
async def client():
    """Async HTTP client bound to the ASGI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health endpoints (public — no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_detailed_health_returns_200(client):
    r = await client.get("/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "components" in data


@pytest.mark.asyncio
async def test_health_ready_returns_200(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_live_returns_200(client):
    r = await client.get("/health/live")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_root_returns_app_info(client):
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "version" in data
    assert "status" in data


# ---------------------------------------------------------------------------
# Authentication enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_route_without_key_returns_401(client):
    r = await client.get("/documents/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_wrong_key_returns_401(client):
    r = await client.get("/documents/", headers={"X-API-Key": "bad-key"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_response_includes_request_id_header(client):
    r = await client.get("/health")
    assert "x-request-id" in r.headers


@pytest.mark.asyncio
async def test_response_includes_process_time_header(client):
    r = await client.get("/health")
    assert "x-process-time" in r.headers


# ---------------------------------------------------------------------------
# AI stub endpoints (Phase 3 routes not yet implemented → 501)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_chat_returns_501(client):
    r = await client.post(
        "/ai/chat",
        json={"message": "Hello"},
        headers=AUTH,
    )
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_ai_completion_returns_501(client):
    r = await client.post(
        "/ai/completion",
        json={"prompt": "Complete this"},
        headers=AUTH,
    )
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_ai_models_returns_501(client):
    r = await client.get("/ai/models", headers=AUTH)
    assert r.status_code == 501


# ---------------------------------------------------------------------------
# Auth stub endpoints (placeholder routes → 501)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_validate_returns_501(client):
    # api_key schema requires min_length=16
    r = await client.post(
        "/auth/validate",
        json={"api_key": "a-valid-key-longer-than-16-chars"},
        headers=AUTH,
    )
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_auth_verify_returns_501(client):
    r = await client.get("/auth/verify", headers=AUTH)
    assert r.status_code == 501


# ---------------------------------------------------------------------------
# Document endpoints — DB mocked via dependency_override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents_returns_200(client):
    """GET /documents/ returns a paginated list (empty in mock)."""
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []

    session = _make_db_session(
        scalar=AsyncMock(return_value=0),
        execute=AsyncMock(return_value=execute_result),
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.get("/documents/", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["documents"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_documents_pagination_params(client):
    """page and page_size query params are accepted."""
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []

    session = _make_db_session(
        scalar=AsyncMock(return_value=0),
        execute=AsyncMock(return_value=execute_result),
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.get("/documents/?page=2&page_size=5", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["page"] == 2
    assert data["page_size"] == 5


@pytest.mark.asyncio
async def test_get_document_not_found_returns_404(client):
    """GET /documents/{id} returns 404 when document does not exist."""
    session = _make_db_session(get=AsyncMock(return_value=None))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.get("/documents/9999", headers=AUTH)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_document_found_returns_200(client):
    """GET /documents/{id} returns document data when found."""
    from app.models.document import DocumentStatus
    import datetime

    # Use plain MagicMock (no spec) so all attributes are reachable
    mock_doc = MagicMock()
    mock_doc.id = 1
    mock_doc.public_id = "abc-123"
    mock_doc.filename = "test.pdf"
    mock_doc.original_filename = "test.pdf"
    mock_doc.file_type = "pdf"
    mock_doc.file_size = 1024
    mock_doc.status = DocumentStatus.COMPLETED
    mock_doc.chunk_count = 5
    mock_doc.error_message = None
    mock_doc.qdrant_collection = "aiva_documents_dev"
    mock_doc.embedding_model = None
    mock_doc.doc_metadata = {}
    mock_doc.created_at = datetime.datetime(2024, 1, 1, 0, 0, 0)
    mock_doc.updated_at = datetime.datetime(2024, 1, 1, 0, 0, 0)

    session = _make_db_session(get=AsyncMock(return_value=mock_doc))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.get("/documents/1", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_document_stats_returns_200(client):
    """GET /documents/stats/overview returns aggregated stats."""
    # execute() is called 3 times with different return shapes
    status_rows = MagicMock()
    status_rows.all.return_value = []

    type_rows = MagicMock()
    type_rows.all.return_value = []

    totals_row = MagicMock()
    totals_row.one.return_value = MagicMock(total=0, total_chunks=0, total_size=0)

    session = _make_db_session(
        execute=AsyncMock(side_effect=[status_rows, type_rows, totals_row])
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.get("/documents/stats/overview", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "total_documents" in data
    assert "total_chunks" in data
    assert data["total_documents"] == 0


@pytest.mark.asyncio
async def test_delete_document_not_found_returns_404(client):
    """DELETE /documents/{id} returns 404 when document does not exist."""
    session = _make_db_session(get=AsyncMock(return_value=None))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    r = await client.delete("/documents/9999", headers=AUTH)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_returns_204(client):
    """DELETE /documents/{id} returns 204 when document exists."""
    from app.models.document import Document

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = 1
    mock_doc.file_path = "/tmp/nonexistent_path/file.pdf"

    session = _make_db_session(
        get=AsyncMock(return_value=mock_doc),
        delete=AsyncMock(),
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    import app.services.vector_store as vs_module
    mock_store = MagicMock()
    mock_store.delete_by_document_id = AsyncMock(return_value=True)
    original = vs_module._vector_store
    vs_module._vector_store = mock_store

    try:
        r = await client.delete("/documents/1", headers=AUTH)
        assert r.status_code == 204
    finally:
        vs_module._vector_store = original


# ---------------------------------------------------------------------------
# Document search endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_documents_returns_200(client):
    """POST /documents/search returns search results."""
    import app.services.search_service as ss_module

    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=[])
    original = ss_module._search_service
    ss_module._search_service = mock_search

    # DB execute for filename resolution (no results → no query needed)
    execute_result = MagicMock()
    execute_result.all.return_value = []
    session = _make_db_session(execute=AsyncMock(return_value=execute_result))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        r = await client.post(
            "/documents/search",
            json={"query": "test query", "limit": 5},
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "results" in data
        assert data["results"] == []
    finally:
        ss_module._search_service = original


@pytest.mark.asyncio
async def test_search_documents_returns_results(client):
    """POST /documents/search returns matched chunks."""
    import app.services.search_service as ss_module

    mock_results = [
        {
            "chunk_id": 1,
            "document_id": 42,
            "content": "Relevant text here",
            "score": 0.87,
            "metadata": {"page": 1},
        }
    ]
    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=mock_results)
    original = ss_module._search_service
    ss_module._search_service = mock_search

    # DB execute for filename resolution
    filename_row = MagicMock()
    filename_row.id = 42
    filename_row.original_filename = "sample.pdf"
    execute_result = MagicMock()
    execute_result.all.return_value = [filename_row]
    session = _make_db_session(execute=AsyncMock(return_value=execute_result))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        r = await client.post(
            "/documents/search",
            json={"query": "relevant text"},
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] == 1
        assert data["results"][0]["content"] == "Relevant text here"
        assert data["results"][0]["filename"] == "sample.pdf"
    finally:
        ss_module._search_service = original


# ---------------------------------------------------------------------------
# Document RAG query endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_documents_returns_200(client):
    """POST /documents/query returns RAG answer."""
    import app.services.rag_service as rs_module
    import app.services.search_service as ss_module
    import app.services.ai_service as ai_module
    import app.services.cache_service as cache_module

    # Set up mock dependencies so RAGService can be created
    ss_module._search_service = MagicMock()
    ai_module._ai_service = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    cache_module._cache_service = mock_cache
    rs_module._rag_service = None

    rag_result = {
        "question": "What is the policy?",
        "answer": "The policy states...",
        "sources": [],
        "confidence": 0.0,
        "context_used": "",
    }

    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(return_value=rag_result)
    rs_module._rag_service = mock_rag

    execute_result = MagicMock()
    execute_result.all.return_value = []
    session = _make_db_session(execute=AsyncMock(return_value=execute_result))

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        r = await client.post(
            "/documents/query",
            json={"question": "What is the policy?"},
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "The policy states..."
        assert data["question"] == "What is the policy?"
        assert "sources" in data
        assert "confidence" in data
    finally:
        rs_module._rag_service = None
        ss_module._search_service = None
        ai_module._ai_service = None
        cache_module._cache_service = None


# ---------------------------------------------------------------------------
# Task status endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_status_returns_200(client):
    """GET /documents/tasks/{task_id} returns task state."""
    # AsyncResult is imported locally inside the function body, so patch at source
    with patch("celery.result.AsyncResult") as mock_result_cls:
        mock_task = MagicMock()
        mock_task.state = "PENDING"
        mock_task.ready.return_value = False
        mock_result_cls.return_value = mock_task

        r = await client.get("/documents/tasks/fake-task-id-123", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "PENDING"
        assert data["task_id"] == "fake-task-id-123"
