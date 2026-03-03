"""
Base Schemas
Common Pydantic schemas used across the application
"""

from typing import Any, Dict, Optional, Generic, TypeVar
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model for all API responses"""

    success: bool = Field(..., description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Optional message")


class ErrorResponse(BaseModel):
    """Error response model"""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Generic success response with data"""

    success: bool = Field(default=True, description="Always true for success")
    message: Optional[str] = Field(None, description="Optional success message")
    data: DataT = Field(..., description="Response data")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated response model"""

    success: bool = Field(default=True)
    data: list[DataT] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
            }
        }


class StatusResponse(BaseModel):
    """Simple status response"""

    status: str = Field(..., description="Status message")
    message: Optional[str] = Field(None, description="Additional information")