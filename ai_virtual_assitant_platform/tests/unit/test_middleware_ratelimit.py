"""
Tests for Rate Limit Middleware
"""

import pytest
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RateLimitMiddleware


@pytest.fixture
def app_with_rate_limit(monkeypatch):
    """Create test app with rate limiting"""
    # Set low limits for testing
    from app.core import settings
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 5)  # 5 requests/minute
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_HOUR", 20)   # 20 requests/hour
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    
    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    # Clear any existing rate limit data before each test
    RateLimitMiddleware._requests.clear()
    
    return app


def test_rate_limit_allows_requests_under_limit(app_with_rate_limit):
    """Test that requests under the limit are allowed"""
    client = TestClient(app_with_rate_limit)
    
    # Make 3 requests (under limit of 5/minute)
    for i in range(3):
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        print(f"  Request {i+1}: Remaining = {response.headers['X-RateLimit-Remaining']}")
    
    print("✓ Requests under limit are allowed")


def test_rate_limit_blocks_requests_over_limit(app_with_rate_limit):
    """Test that requests over the limit are blocked"""
    client = TestClient(app_with_rate_limit)
    
    # Make 5 requests (at the limit)
    for i in range(5):
        response = client.get("/api/test")
        assert response.status_code == 200
    
    # 6th request should be blocked
    response = client.get("/api/test")
    assert response.status_code == 429
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in response.headers
    
    print("✓ Requests over limit are blocked with 429")


def test_rate_limit_headers_present(app_with_rate_limit):
    """Test that rate limit headers are present in responses"""
    client = TestClient(app_with_rate_limit)
    
    response = client.get("/api/test")
    
    # Check all required headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    
    limit = int(response.headers["X-RateLimit-Limit"])
    remaining = int(response.headers["X-RateLimit-Remaining"])
    reset = int(response.headers["X-RateLimit-Reset"])
    
    assert limit == 5  # Our test limit
    assert remaining >= 0
    assert reset > time.time()  # Reset time is in the future
    
    print(f"✓ Rate limit headers present: Limit={limit}, Remaining={remaining}")


def test_rate_limit_skips_public_paths(app_with_rate_limit):
    """Test that public paths are not rate limited"""
    client = TestClient(app_with_rate_limit)
    
    # Make many requests to /health (public path)
    for i in range(10):  # More than the limit
        response = client.get("/health")
        assert response.status_code == 200
    
    print("✓ Public paths not rate limited (made 10 requests to /health)")


def test_rate_limit_resets_after_time(app_with_rate_limit):
    """Test that rate limit resets after the time window"""
    # Note: This test would need to wait 60 seconds in real time
    # For now, we'll just verify the reset time is set correctly
    client = TestClient(app_with_rate_limit)
    
    response = client.get("/api/test")
    reset_time = int(response.headers["X-RateLimit-Reset"])
    current_time = int(time.time())
    
    # Reset should be within next 60 seconds
    assert reset_time > current_time
    assert reset_time <= current_time + 60
    
    print(f"✓ Reset time set correctly (in {reset_time - current_time}s)")


def test_rate_limit_tracks_remaining_correctly(app_with_rate_limit):
    """Test that remaining count decreases correctly"""
    client = TestClient(app_with_rate_limit)
    
    # Make requests and track remaining
    remaining_counts = []
    for i in range(5):
        response = client.get("/api/test")
        if response.status_code == 200:
            remaining = int(response.headers["X-RateLimit-Remaining"])
            remaining_counts.append(remaining)
            print(f"  Request {i+1}: {remaining} remaining")
    
    # Remaining should decrease
    assert remaining_counts[0] > remaining_counts[-1]
    assert remaining_counts[-1] == 0  # Last request should have 0 remaining
    
    print("✓ Remaining count decreases correctly")


def test_rate_limit_can_be_disabled(monkeypatch):
    """Test that rate limiting can be disabled"""
    from app.core import settings
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    
    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}
    
    client = TestClient(app)
    
    # Make many requests (should all work because rate limiting is disabled)
    for i in range(20):
        response = client.get("/api/test")
        assert response.status_code == 200
    
    print("✓ Rate limiting can be disabled via settings")