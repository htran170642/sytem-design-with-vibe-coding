"""
Schemas package
Contains Pydantic schemas for request/response validation
"""

from app.schemas.base import (
    BaseResponse,
    ErrorResponse,
    SuccessResponse,
    PaginatedResponse,
    StatusResponse,
)
from app.schemas.ai import (
    Message,
    ChatRequest,
    ChatResponse,
    CompletionRequest,
    CompletionResponse,
)
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentMetadata,
    DocumentQueryRequest,
    DocumentQueryResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    SearchResult,
    DocumentListResponse,
    DocumentStats,
)
from app.schemas.auth import TokenResponse, APIKeyRequest, APIKeyResponse

__all__ = [
    # Base
    "BaseResponse",
    "ErrorResponse",
    "SuccessResponse",
    "PaginatedResponse",
    "StatusResponse",
    # AI
    "Message",
    "ChatRequest",
    "ChatResponse",
    "CompletionRequest",
    "CompletionResponse",
    # Document
    "DocumentUploadResponse",
    "DocumentResponse",
    "DocumentMetadata",
    "DocumentQueryRequest",
    "DocumentQueryResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "SearchResult",
    "DocumentListResponse",
    "DocumentStats",
    # Auth
    "TokenResponse",
    "APIKeyRequest",
    "APIKeyResponse",
]