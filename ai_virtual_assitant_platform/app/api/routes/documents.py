"""
Document Routes
API endpoints for document upload and management
Phase 4, Step 1: Implement document upload API
Phase 7: Database & Persistence — implement all stub routes
"""

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.db import get_db
from app.models.document import Document, DocumentStatus
from app.schemas.document import (
    DocumentListResponse,
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentResponse,
    DocumentStats,
    DocumentUploadResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.services.rag_service import get_rag_service
from app.services.search_service import get_search_service

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(settings.UPLOAD_DIR).resolve()
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_file(file: UploadFile) -> str:
    """Validate uploaded file and return file type string."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    return {
        ".pdf": "pdf",
        ".docx": "docx",
        ".txt": "txt",
        ".html": "html",
        ".md": "md",
    }[file_ext]


async def save_upload_file(file: UploadFile, destination: Path) -> int:
    """Save uploaded file to disk; return file size in bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_size = 0
    chunk_size = 1024 * 1024  # 1 MB

    with open(destination, "wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                os.remove(destination)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max: {MAX_FILE_SIZE // 1024 // 1024}MB",
                )
            f.write(chunk)

    return file_size


def _doc_not_found(document_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Document {document_id} not found")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for processing.

    Supported: PDF, DOCX, TXT, HTML, Markdown. Max size: 10 MB.
    The file is saved to disk and a background Celery task handles
    extraction → chunking → embedding → Qdrant upsert.
    """
    try:
        file_type = validate_file(file)
        doc_uuid = str(uuid.uuid4())
        file_path = UPLOAD_DIR / doc_uuid / file.filename
        file_size = await save_upload_file(file, file_path)

        # Persist document record before triggering Celery so the task can
        # update status via the real DB id.
        doc = Document(
            public_id=doc_uuid,
            filename=file.filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_type=file_type,
            file_size=file_size,
            status=DocumentStatus.PENDING,
            qdrant_collection=settings.QDRANT_COLLECTION_NAME,
        )
        db.add(doc)
        await db.flush()   # assign doc.id without closing the transaction
        await db.refresh(doc)

        logger.info(
            "Document record created",
            extra={
                "doc_id": doc.id,
                "public_id": doc_uuid,
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": file_size,
            },
        )

        # Trigger background processing
        from app.tasks.document_tasks import process_document_task

        task = process_document_task.delay(
            document_id=doc.id,
            file_path=str(file_path),
            file_type=file_type,
        )

        logger.info(
            "Background processing triggered",
            extra={"doc_id": doc.id, "task_id": task.id},
        )

        return DocumentUploadResponse(
            id=doc.id,
            filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            status=DocumentStatus.PENDING,
            message=f"Document uploaded. Processing started (task: {task.id[:8]}...)",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/stats/overview", response_model=DocumentStats)
async def get_document_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics across all documents."""
    # Counts by status
    status_rows = (
        await db.execute(
            select(Document.status, func.count().label("n"))
            .group_by(Document.status)
        )
    ).all()
    by_status = {row.status: row.n for row in status_rows}

    # Counts by file type
    type_rows = (
        await db.execute(
            select(Document.file_type, func.count().label("n"))
            .group_by(Document.file_type)
        )
    ).all()
    by_type = {row.file_type: row.n for row in type_rows}

    # Totals
    totals = (
        await db.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(Document.chunk_count), 0).label("total_chunks"),
                func.coalesce(func.sum(Document.file_size), 0).label("total_size"),
            )
        )
    ).one()

    total_docs = totals.total
    total_chunks = int(totals.total_chunks)
    avg_chunks = round(total_chunks / total_docs, 2) if total_docs > 0 else 0.0

    return DocumentStats(
        total_documents=total_docs,
        total_chunks=total_chunks,
        by_status=by_status,
        by_type=by_type,
        total_size_bytes=int(totals.total_size),
        avg_chunks_per_doc=avg_chunks,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Get document metadata by ID."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise _doc_not_found(document_id)
    return DocumentResponse.model_validate(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    file_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List documents with optional status/file_type filters and pagination."""
    query = select(Document).order_by(Document.created_at.desc())
    if status:
        query = query.where(Document.status == status)
    if file_type:
        query = query.where(Document.file_type == file_type)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )
    docs = (
        await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete a document: removes the DB record, Qdrant vectors, and uploaded file.
    """
    doc = await db.get(Document, document_id)
    if not doc:
        raise _doc_not_found(document_id)

    # Remove vectors from Qdrant (best-effort)
    try:
        from app.services.vector_store import get_vector_store

        vector_store = get_vector_store()
        await vector_store.delete_by_document_id(document_id)
    except Exception as e:
        logger.warning(f"Qdrant delete failed for doc {document_id}: {e}")

    # Remove file from disk (best-effort)
    try:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
        # Remove parent dir if empty
        if file_path.parent.exists() and not any(file_path.parent.iterdir()):
            file_path.parent.rmdir()
    except Exception as e:
        logger.warning(f"File delete failed for doc {document_id}: {e}")

    await db.delete(doc)
    # 204 — no body


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Get background task status.

    Returns Celery task state (PENDING, PROCESSING, SUCCESS, FAILURE) and progress.
    """
    from celery.result import AsyncResult

    from app.core.celery_app import celery_app

    task = AsyncResult(task_id, app=celery_app)

    # Celery backend can raise ValueError when deserializing a malformed
    # failure result (e.g. after a retry storm or backend mismatch).
    try:
        state = task.state
    except (ValueError, KeyError):
        state = "UNKNOWN"

    response: dict = {"task_id": task_id, "state": state}

    try:
        response["ready"] = task.ready()
        if state == "PENDING":
            response["status"] = "Task is waiting to be processed"
        elif state == "PROCESSING":
            response["status"] = "Task is being processed"
            response["progress"] = task.info.get("progress", 0) if task.info else 0
            response["current_step"] = task.info.get("step", "") if task.info else ""
        elif state == "SUCCESS":
            response["status"] = "Task completed successfully"
            response["result"] = task.result
        elif state in ("FAILURE", "UNKNOWN"):
            response["status"] = "Task failed"
            try:
                response["error"] = str(task.info)
            except Exception:
                response["error"] = "Could not deserialize error details"
        else:
            response["status"] = state
    except Exception as exc:
        response["status"] = "Could not read task details"
        response["error"] = str(exc)

    return response


@router.post("/search", response_model=DocumentQueryResponse)
async def search_documents(
    request: DocumentQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search across documents.

    Performs similarity search using embeddings and returns matching chunks
    sorted by similarity score.
    """
    try:
        search_service = get_search_service()
        results = await search_service.search(
            query=request.query,
            limit=request.limit,
            document_ids=request.document_ids,
            min_score=request.min_score,
        )

        # Resolve actual filenames from DB
        doc_id_to_filename: dict[int, str] = {}
        doc_ids = {r["document_id"] for r in results}
        if doc_ids:
            rows = (
                await db.execute(
                    select(Document.id, Document.original_filename).where(
                        Document.id.in_(doc_ids)
                    )
                )
            ).all()
            doc_id_to_filename = {row.id: row.original_filename for row in rows}

        from app.schemas.document import SearchResult

        search_results = [
            SearchResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                filename=doc_id_to_filename.get(r["document_id"], f"document_{r['document_id']}"),
                content=r["content"],
                score=r["score"],
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]

        return DocumentQueryResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/query", response_model=RAGQueryResponse)
async def query_documents(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Answer questions using RAG (Retrieval Augmented Generation).

    Combines semantic search with AI to answer questions based on document content.
    """
    try:
        rag_service = get_rag_service()
        result = await rag_service.query(
            question=request.question,
            document_ids=request.document_ids,
            top_k=request.top_k,
            min_score=request.min_score,
            temperature=request.temperature,
        )

        # Resolve actual filenames from DB
        doc_id_to_filename: dict[int, str] = {}
        doc_ids = {s["document_id"] for s in result["sources"]}
        if doc_ids:
            rows = (
                await db.execute(
                    select(Document.id, Document.original_filename).where(
                        Document.id.in_(doc_ids)
                    )
                )
            ).all()
            doc_id_to_filename = {row.id: row.original_filename for row in rows}

        from app.schemas.document import SearchResultWithSource

        sources = [
            SearchResultWithSource(
                chunk_id=s["chunk_id"],
                document_id=s["document_id"],
                filename=doc_id_to_filename.get(s["document_id"], f"document_{s['document_id']}"),
                content=s["content"],
                score=s["score"],
                page=s.get("metadata", {}).get("page"),
                section=s.get("metadata", {}).get("section"),
            )
            for s in result["sources"]
        ]

        return RAGQueryResponse(
            question=result["question"],
            answer=result["answer"],
            sources=sources,
            confidence=result["confidence"],
            total_chunks_searched=len(result["sources"]),
        )

    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Query failed")
