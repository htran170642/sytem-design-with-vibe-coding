"""
Document ORM Model
SQLAlchemy 2.0 declarative model for document storage.
Phase 7: Database & Persistence
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """
    Stores metadata for every uploaded document.

    The real content lives in Qdrant (vector embeddings). This table
    provides structured metadata, status tracking, and enables the
    list / get / delete / stats API routes.
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_created_at", "created_at"),
    )

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identity
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)

    # File info
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Processing state
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentStatus.PENDING
    )
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qdrant_collection: Mapped[str] = mapped_column(String(255), nullable=False)

    # Extracted metadata (author, pages, word_count, …)
    doc_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Error info
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"Document(id={self.id}, filename={self.filename!r}, status={self.status!r})"
        )
