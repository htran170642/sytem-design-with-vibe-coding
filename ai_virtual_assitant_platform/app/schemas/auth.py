"""
Authentication Schemas
Pydantic schemas for authentication endpoints
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }


class APIKeyRequest(BaseModel):
    """Request to validate API key"""

    api_key: str = Field(..., min_length=16, description="API key to validate")


class APIKeyResponse(BaseModel):
    """API key validation response"""

    valid: bool = Field(..., description="Whether the API key is valid")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    rate_limit: Optional[int] = Field(None, description="Rate limit for this key")

    class Config:
        json_schema_extra = {
            "example": {"valid": True, "user_id": "user_123", "rate_limit": 1000}
        }