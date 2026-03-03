"""
Tests for Request Logging Middleware
"""

import pytest
import time
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware


def test_request_logging_middleware(caplog):
    """Test that request logging middleware logs requests AND adds timing header"""
    
    # Create a test app
    app = FastAPI()
    
    # Add both middlewares
    # ORDER MATTERS: RequestIDMiddleware first, then RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)  # This runs second
    app.add_middleware(RequestIDMiddleware)       # This runs first
    
    # Create a test route
    @app.get("/test")
    async def test_route():
        return {"message": "success"}
    
    # Create test client
    client = TestClient(app)
    
    # Clear any existing logs
    caplog.clear()
    
    # Make a request
    with caplog.at_level("INFO"):
        response = client.get("/test?page=1&limit=10")
    
    # Check response
    assert response.status_code == 200
    
    # Check that X-Process-Time header was added
    assert "X-Process-Time" in response.headers
    process_time = float(response.headers["X-Process-Time"])
    assert process_time > 0
    
    # Check that logs were created
    # Should have 2 log messages: "Request started" and "Request completed"
    log_messages = [record.message for record in caplog.records]
    
    # Find the started and completed messages
    started_msg = [msg for msg in log_messages if "Request started" in msg]
    completed_msg = [msg for msg in log_messages if "Request completed" in msg]
    
    assert len(started_msg) >= 1, "Should log request started"
    assert len(completed_msg) >= 1, "Should log request completed"
    
    # Check the content
    assert "GET" in started_msg[0]
    assert "/test" in started_msg[0]
    
    assert "GET" in completed_msg[0]
    assert "/test" in completed_msg[0]
    assert "200" in completed_msg[0]
    
    print(f"✓ Request logging middleware logs correctly AND adds timing header ({process_time}s)")



def test_logging_includes_request_id(caplog):
    """Test that logs include the request ID"""
    
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    
    @app.get("/test")
    async def test_route(request: Request):
        return {"request_id": request.state.request_id}
    
    client = TestClient(app)
    
    caplog.clear()
    
    with caplog.at_level("INFO"):
        response = client.get("/test")
    
    # Get the request ID from response
    request_id = response.json()["request_id"]
    
    # Check that the request ID appears in the logs
    # The request_id is stored in the log record's extra data
    found_in_logs = False
    for record in caplog.records:
        if hasattr(record, "request_id") and record.request_id == request_id:
            found_in_logs = True
            break
    
    assert found_in_logs, f"Request ID {request_id} should appear in logs"
    
    print(f"✓ Logs include request ID: {request_id}")


def test_logging_includes_duration(caplog):
    """Test that logs include request duration"""
    
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    
    @app.get("/slow")
    async def slow_route():
        # Simulate a slow operation
        time.sleep(0.1)  # 100ms
        return {"message": "done"}
    
    client = TestClient(app)
    
    caplog.clear()
    
    with caplog.at_level("INFO"):
        response = client.get("/slow")
    
    # Check that duration was logged
    found_duration = False
    for record in caplog.records:
        if hasattr(record, "duration_ms"):
            duration = record.duration_ms
            # Duration should be at least 100ms (we slept for 100ms)
            assert duration >= 100, f"Duration {duration}ms should be >= 100ms"
            found_duration = True
            print(f"✓ Request took {duration}ms (expected >= 100ms)")
            break
    
    assert found_duration, "Duration should be logged"