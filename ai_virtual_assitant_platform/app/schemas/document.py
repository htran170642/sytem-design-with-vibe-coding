"""
Document Schemas
Pydantic models for document API validation
Phase 4, Step 1: Document upload and validation
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field, validator


# ============================================
# Request Schemas
# ============================================

class DocumentUploadRequest(BaseModel):
    """Document upload request"""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., description="MIME type")
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename has proper extension"""
        allowed_extensions = {'.pdf', '.docx', '.txt', '.html', '.md'}
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(
                f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        return v


class DocumentQueryRequest(BaseModel):
    """Query documents with semantic search"""
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20, description="Max results")
    document_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by specific documents"
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score"
    )


class RAGQueryRequest(BaseModel):
    """RAG query request - ask questions about documents"""
    question: str = Field(..., min_length=1, max_length=1000, description="Question to ask")
    document_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by specific documents"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score"
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="LLM temperature (lower = more factual)"
    )


# ============================================
# Response Schemas
# ============================================

class DocumentMetadata(BaseModel):
    """Document metadata"""
    pages: Optional[int] = None
    author: Optional[str] = None
    title: Optional[str] = None
    created_date: Optional[str] = None
    word_count: Optional[int] = None
    language: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional fields


class DocumentResponse(BaseModel):
    """Document response"""
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: Optional[int] = None
    embedding_model: Optional[str] = None
    # ORM column is 'doc_metadata'; validation_alias lets pydantic read it correctly
    metadata: Optional[Dict[str, Any]] = Field(None, validation_alias="doc_metadata")
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentUploadResponse(BaseModel):
    """Upload response"""
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    message: str = "Document uploaded successfully"


class DocumentChunkResponse(BaseModel):
    """Document chunk response"""
    id: int
    document_id: int
    chunk_index: int
    content: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Single search result from semantic search"""
    chunk_id: int
    document_id: int
    filename: str
    content: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


class SearchResultWithSource(BaseModel):
    """Search result with citation info"""
    chunk_id: int
    document_id: int
    filename: str
    content: str
    score: float
    page: Optional[int] = None
    section: Optional[str] = None


class DocumentQueryResponse(BaseModel):
    """Semantic search response"""
    query: str
    results: List[SearchResult]
    total_results: int


class RAGQueryResponse(BaseModel):
    """RAG query response with answer and sources"""
    question: str
    answer: str
    sources: List[SearchResultWithSource]
    confidence: float = Field(description="Confidence score (0-1)")
    total_chunks_searched: int


class DocumentListResponse(BaseModel):
    """List of documents with pagination"""
    documents: List[DocumentResponse]
    total: int
    page: int = 1
    page_size: int = 10


# ============================================
# Stats and Analytics
# ============================================

class DocumentStats(BaseModel):
    """Document statistics and analytics"""
    total_documents: int = Field(description="Total number of documents")
    total_chunks: int = Field(description="Total number of text chunks")
    by_status: Dict[str, int] = Field(
        description="Document count by status",
        example={
            "pending": 5,
            "processing": 2,
            "completed": 10,
            "failed": 1
        }
    )
    by_type: Dict[str, int] = Field(
        description="Document count by file type",
        example={
            "pdf": 8,
            "docx": 5,
            "txt": 3,
            "html": 1,
            "md": 1
        }
    )
    total_size_bytes: int = Field(description="Total storage used in bytes")
    avg_chunks_per_doc: float = Field(description="Average chunks per document")
    total_embeddings: int = Field(default=0, description="Total embeddings generated")


class ProcessingStatus(BaseModel):
    """Document processing status"""
    document_id: int
    filename: str
    status: str
    progress: float = Field(ge=0.0, le=1.0, description="Processing progress (0-1)")
    current_step: str = Field(
        description="Current processing step",
        example="extracting_text"
    )
    error_message: Optional[str] = None
    estimated_completion: Optional[datetime] = None