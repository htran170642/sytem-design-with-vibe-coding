"""
Tests for Request ID Middleware
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.middleware import RequestIDMiddleware


def test_request_id_middleware():
    """Test that request ID middleware adds unique IDs to requests"""
    
    # Create a test app
    app = FastAPI()
    
    # Add our middleware
    app.add_middleware(RequestIDMiddleware)
    
    # Create a test route that returns the request ID
    @app.get("/test")
    async def test_route(request: Request):
        # Access the request ID from request.state
        return {"request_id": request.state.request_id}
    
    # Create test client
    client = TestClient(app)
    
    # Make a request
    response = client.get("/test")
    
    # Check status
    assert response.status_code == 200
    
    # Check that response has X-Request-ID header
    assert "X-Request-ID" in response.headers
    request_id_header = response.headers["X-Request-ID"]
    
    # Check format (should start with "req_")
    assert request_id_header.startswith("req_")
    
    # Check that request ID is in response body (from our test route)
    data = response.json()
    assert "request_id" in data
    request_id_body = data["request_id"]
    
    # Both should be the same
    assert request_id_header == request_id_body
    
    print(f"✓ Request ID generated: {request_id_header}")


def test_unique_request_ids():
    """Test that each request gets a different ID"""
    
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    
    @app.get("/test")
    async def test_route(request: Request):
        return {"request_id": request.state.request_id}
    
    client = TestClient(app)
    
    # Make 5 requests
    request_ids = []
    for i in range(5):
        response = client.get("/test")
        request_id = response.headers["X-Request-ID"]
        request_ids.append(request_id)
        print(f"Request {i+1}: {request_id}")
    
    # All request IDs should be unique
    assert len(request_ids) == len(set(request_ids))
    print(f"✓ All {len(request_ids)} request IDs are unique")