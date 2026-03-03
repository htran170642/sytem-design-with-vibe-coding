"""
Tests for Exception Handling
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AIVAException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    LLMError,
)
from app.core.exception_handlers import register_exception_handlers


# Create a test app
@pytest.fixture
def test_app():
    """Create a test FastAPI app with exception handlers"""
    app = FastAPI()
    register_exception_handlers(app)
    
    # Add test endpoints
    @app.get("/test/aiva-exception")
    async def test_aiva_exception():
        raise AIVAException(
            message="Test AIVA exception",
            status_code=500,
            error_code="TEST_ERROR",
        )
    
    @app.get("/test/validation-error")
    async def test_validation_error():
        raise ValidationError(
            message="Test validation error",
            details={"field": "test_field"},
        )
    
    @app.get("/test/auth-error")
    async def test_auth_error():
        raise AuthenticationError()
    
    @app.get("/test/not-found")
    async def test_not_found():
        raise NotFoundError(resource="Document", resource_id="doc_123")
    
    @app.get("/test/rate-limit")
    async def test_rate_limit():
        raise RateLimitError(retry_after=60)
    
    @app.get("/test/llm-error")
    async def test_llm_error():
        raise LLMError(message="API quota exceeded")
    
    @app.get("/test/unexpected-error")
    async def test_unexpected_error():
        raise ValueError("Unexpected error occurred")
    
    # Pydantic validation test
    class TestModel(BaseModel):
        name: str = Field(..., min_length=3)
        age: int = Field(..., ge=0, le=120)
    
    @app.post("/test/pydantic-validation")
    async def test_pydantic_validation(data: TestModel):
        return {"message": "Success"}
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


class TestExceptionHandlers:
    """Test exception handlers"""

    def test_aiva_exception_handler(self, client):
        """Test AIVA exception handler"""
        response = client.get("/test/aiva-exception")
        
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "TEST_ERROR"
        assert data["message"] == "Test AIVA exception"
    
    def test_validation_error_handler(self, client):
        """Test validation error handler"""
        response = client.get("/test/validation-error")
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "VALIDATION_ERROR"
        assert "field" in data["detail"]
    
    def test_authentication_error_handler(self, client):
        """Test authentication error handler"""
        response = client.get("/test/auth-error")
        
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "AUTHENTICATION_ERROR"
    
    def test_not_found_error_handler(self, client):
        """Test not found error handler"""
        response = client.get("/test/not-found")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "NOT_FOUND"
        assert "Document" in data["message"]
        assert "doc_123" in data["message"]
    
    def test_rate_limit_error_handler(self, client):
        """Test rate limit error handler"""
        response = client.get("/test/rate-limit")
        
        assert response.status_code == 429
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "RATE_LIMIT_EXCEEDED"
        assert data["detail"]["retry_after"] == 60
    
    def test_llm_error_handler(self, client):
        """Test LLM error handler"""
        response = client.get("/test/llm-error")
        
        assert response.status_code == 502
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "EXTERNAL_SERVICE_ERROR"
        assert "LLM" in data["message"]


def test_exception_handlers_registered():
    """Test that exception handlers can be registered"""
    from app.main import app
    
    # App should have exception handlers registered
    assert len(app.exception_handlers) > 0