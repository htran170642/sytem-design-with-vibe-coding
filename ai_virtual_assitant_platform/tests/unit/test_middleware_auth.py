"""
Tests for API Key Authentication Middleware
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.middleware import APIKeyAuthMiddleware


@pytest.fixture
def app_with_auth():
    """Create test app with authentication middleware"""
    app = FastAPI()
    app.add_middleware(APIKeyAuthMiddleware)
    
    # Public endpoint (no auth required)
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    # Protected endpoint (auth required)
    @app.get("/api/users")
    async def get_users(request: Request):
        # Can access the validated API key
        api_key = request.state.api_key
        return {"users": ["Alice", "Bob"], "api_key_prefix": api_key[:8]}
    
    return app


def test_public_path_no_auth_required(app_with_auth):
    """Test that public paths don't require authentication"""
    client = TestClient(app_with_auth)
    
    # No API key provided
    response = client.get("/health")
    
    # Should still work
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    print("✓ Public paths accessible without API key")


def test_protected_path_requires_api_key(app_with_auth):
    """Test that protected paths require API key"""
    client = TestClient(app_with_auth)
    
    # No API key provided
    response = client.get("/api/users")
    
    # Should return 401
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "AUTHENTICATION_ERROR"
    assert "API key required" in data["message"]
    
    print("✓ Protected paths reject requests without API key")


def test_invalid_api_key_rejected(app_with_auth):
    """Test that invalid API key is rejected"""
    client = TestClient(app_with_auth)
    
    # Wrong API key
    response = client.get(
        "/api/users",
        headers={"X-API-Key": "wrong-key-12345"}
    )
    
    # Should return 401
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "AUTHENTICATION_ERROR"
    assert "Invalid API key" in data["message"]
    
    print("✓ Invalid API keys are rejected")


def test_valid_api_key_accepted(app_with_auth, monkeypatch):
    """Test that valid API key allows access"""
    # Set the API key in settings
    from app.core import settings
    test_api_key = "test-api-key-12345"
    monkeypatch.setattr(settings, "API_KEY", test_api_key)
    
    client = TestClient(app_with_auth)
    
    # Correct API key
    response = client.get(
        "/api/users",
        headers={"X-API-Key": test_api_key}
    )
    
    # Should work
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert len(data["users"]) == 2
    
    print(f"✓ Valid API key accepted: {test_api_key[:8]}...")


def test_api_key_stored_in_request_state(app_with_auth, monkeypatch):
    """Test that validated API key is stored in request.state"""
    from app.core import settings
    test_api_key = "test-api-key-12345"
    monkeypatch.setattr(settings, "API_KEY", test_api_key)
    
    client = TestClient(app_with_auth)
    
    response = client.get(
        "/api/users",
        headers={"X-API-Key": test_api_key}
    )
    
    # Route handler should have access to API key via request.state
    data = response.json()
    assert "api_key_prefix" in data
    assert data["api_key_prefix"] == test_api_key[:8]
    
    print("✓ API key accessible in route handlers via request.state")


def test_all_public_paths(app_with_auth):
    """Test that all defined public paths work without auth"""
    client = TestClient(app_with_auth)
    
    # Public paths that should work
    public_paths = ["/", "/health"]
    
    for path in public_paths:
        # Some paths might return 404 if not defined, but should NOT return 401
        response = client.get(path)
        assert response.status_code != 401, f"Path {path} should be public but returned 401"
    
    print(f"✓ All {len(public_paths)} public paths accessible without auth")