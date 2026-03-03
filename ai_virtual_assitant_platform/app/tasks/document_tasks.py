"""
Document Processing Tasks
Celery tasks for background document processing
Phase 5: Background Jobs & Async Processing
Phase 7: Persist processing status to PostgreSQL
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from celery import Task
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.services.extractors import extract_text
from app.services.text_chunker import get_text_chunker
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# DB helper — used inside Celery tasks via loop.run_until_complete()
# ---------------------------------------------------------------------------


async def _update_db_status(
    doc_id: int,
    status: str,
    chunk_count: Optional[int] = None,
    embedding_model: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update document status in PostgreSQL (async, called from within the task's event loop)."""
    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            logger.warning(f"Document {doc_id} not found in DB during status update")
            return
        doc.status = status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if embedding_model is not None:
            doc.embedding_model = embedding_model
        if error_message is not None:
            doc.error_message = error_message
        await session.commit()
        logger.debug(f"Document {doc_id} status updated to '{status}'")


class CallbackTask(Task):
    """
    Base task with callbacks for tracking progress
    """
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        logger.info(f"Task {task_id} succeeded")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        logger.error(f"Task {task_id} failed: {exc}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried"""
        logger.warning(f"Task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="process_document",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def process_document_task(
    self,
    document_id: int,
    file_path: str,
    file_type: str,
) -> Dict[str, Any]:
    """
    Process document in background: extract → chunk → embed → store
    
    Args:
        document_id: Document ID
        file_path: Path to uploaded file
        file_type: File type (pdf, docx, txt, html, md)
        
    Returns:
        Processing result with stats
        
    Raises:
        Exception: If processing fails (will retry)
    """
    logger.info(
        f"Starting document processing",
        extra={
            "document_id": document_id,
            "file_path": file_path,
            "file_type": file_type,
        }
    )
    
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Update task state
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "extracting_text",
                "progress": 0.1,
                "document_id": document_id,
            }
        )

        # Persist status → processing
        loop.run_until_complete(
            _update_db_status(document_id, DocumentStatus.PROCESSING)
        )

        # Step 1: Extract text
        start_time = time.time()
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        text, metadata = extract_text(file_path_obj, file_type)

        logger.info(
            f"Text extracted",
            extra={
                "document_id": document_id,
                "word_count": metadata.get("word_count", 0),
                "duration": time.time() - start_time,
            }
        )

        # Update progress
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "chunking_text",
                "progress": 0.3,
                "document_id": document_id,
                "text_length": len(text),
            }
        )

        # Step 2: Chunk text
        chunker = get_text_chunker()
        chunks = chunker.chunk_text(text, metadata=metadata)

        logger.info(
            f"Text chunked",
            extra={
                "document_id": document_id,
                "chunk_count": len(chunks),
            }
        )

        # Update progress
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "generating_embeddings",
                "progress": 0.5,
                "document_id": document_id,
                "chunk_count": len(chunks),
            }
        )

        # Step 3: Generate embeddings
        embedding_service = get_embedding_service()
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        embeddings = loop.run_until_complete(
            embedding_service.generate_embeddings_batch(chunk_texts)
        )
        
        logger.info(
            f"Embeddings generated",
            extra={
                "document_id": document_id,
                "embedding_count": len(embeddings),
            }
        )
        
        # Update progress
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "storing_vectors",
                "progress": 0.8,
                "document_id": document_id,
            }
        )
        
        # Step 4: Store in vector database
        vector_store = get_vector_store()
        
        chunk_ids = [
            document_id * 10000 + i
            for i in range(len(chunks))
        ]
        
        metadata_list = [
            {
                "document_id": document_id,
                "content": chunk["text"],
                "metadata": chunk.get("metadata", {}),
            }
            for chunk in chunks
        ]
        
        loop.run_until_complete(
            vector_store.upsert_embeddings(
                embeddings=embeddings,
                chunk_ids=chunk_ids,
                metadata=metadata_list,
            )
        )

        logger.info(
            f"Vectors stored",
            extra={
                "document_id": document_id,
                "vector_count": len(embeddings),
            }
        )

        # Calculate stats
        total_time = time.time() - start_time
        total_tokens = sum(chunk["tokens"] for chunk in chunks)

        # Persist status → completed
        loop.run_until_complete(
            _update_db_status(
                document_id,
                DocumentStatus.COMPLETED,
                chunk_count=len(chunks),
                embedding_model=settings.EMBEDDING_MODEL,
            )
        )

        loop.close()

        result = {
            "status": "completed",
            "document_id": document_id,
            "chunks": len(chunks),
            "embeddings": len(embeddings),
            "total_tokens": total_tokens,
            "processing_time_seconds": round(total_time, 2),
            "cost_usd": embedding_service.estimate_cost(total_tokens),
        }

        logger.info(
            f"Document processing completed",
            extra=result
        )

        return result

    except Exception as e:
        logger.error(
            f"Document processing failed",
            extra={
                "document_id": document_id,
                "error": str(e),
            },
            exc_info=True
        )

        # Persist status → failed
        try:
            loop.run_until_complete(
                _update_db_status(
                    document_id,
                    DocumentStatus.FAILED,
                    error_message=str(e),
                )
            )
        except Exception as db_exc:
            logger.warning(f"Failed to update DB status to failed: {db_exc}")

        if not loop.is_closed():
            loop.close()

        # Update state to failed
        self.update_state(
            state="FAILURE",
            meta={
                "document_id": document_id,
                "error": str(e),
            }
        )
        
        raise  # Re-raise to trigger retry


@celery_app.task(name="get_task_status")
def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get status of a Celery task
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status information
    """
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    return {
        "task_id": task_id,
        "state": result.state,
        "info": result.info,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }