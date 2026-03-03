"""
Middleware Components
Request processing middleware for AIVA application
"""

import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records Prometheus HTTP metrics.

    Records:
    - aiva_http_requests_total (method, path, status_code)
    - aiva_http_request_duration_seconds (method, path)
    - aiva_active_http_requests gauge
    - aiva_http_errors_total for 4xx/5xx responses

    Health and metrics paths are excluded to avoid noise.
    """

    # Exclude high-frequency health / scrape paths from histograms
    EXCLUDE_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        from app.services.metrics_service import (
            active_http_requests,
            http_errors_total,
            http_request_duration_seconds,
            http_requests_total,
        )

        path = request.url.path
        method = request.method

        active_http_requests.inc()
        start_time = time.time()
        try:
            response = await call_next(request)
        finally:
            active_http_requests.dec()

        duration = time.time() - start_time
        status = str(response.status_code)

        http_requests_total.labels(method=method, path=path, status_code=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

        if response.status_code >= 400:
            http_errors_total.labels(method=method, path=path, status_code=status).inc()

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request
    
    The request ID:
    - Is generated for each incoming request
    - Is stored in request.state for access in route handlers
    - Is added to response headers
    - Can be used for log correlation and tracing
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add request ID
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response with X-Request-ID header
        """
        # Generate a unique request ID
        # Format: req_<random-uuid>
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Store request ID in request.state so route handlers can access it
        # Usage in routes: request.state.request_id
        request.state.request_id = request_id
        
        # Call the next middleware or route handler
        response = await call_next(request)
        
        # Add request ID to response headers
        # This allows clients to reference the request ID when reporting issues
        response.headers["X-Request-ID"] = request_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all incoming requests and responses
    AND adds process time to response headers
    
    This middleware combines:
    - Request/response logging with structured data
    - Process time measurement and header addition
    
    Logs include:
    - Request method and path
    - Request ID (if available)
    - Response status code
    - Request duration
    - Client IP address
    
    Response headers include:
    - X-Process-Time: Duration in seconds
    
    This middleware should be added AFTER RequestIDMiddleware
    so it can access the request ID
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request, log it, and add timing header
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response from the route handler with X-Process-Time header
        """
        # Get request ID if it exists (from RequestIDMiddleware)
        # If RequestIDMiddleware hasn't run yet, request_id will be None
        request_id = getattr(request.state, "request_id", None)
        
        # Get client IP address
        # request.client.host gives the IP address of the client
        client_host = request.client.host if request.client else "unknown"
        
        # Log request started
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": client_host,
            },
        )
        
        # Record start time (SINGLE measurement for both logging and header)
        start_time = time.time()
        
        # Process the request
        # This is where your route handler runs
        response = await call_next(request)
        
        # Calculate duration (ONCE, used for both logging and header)
        # time.time() gives current time in seconds
        # Subtract start_time to get duration
        duration = time.time() - start_time
        
        # Add process time to response headers
        # Format: X-Process-Time: 0.123456 (in seconds)
        response.headers["X-Process-Time"] = str(round(duration, 6))
        
        # Log request completed
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),  # Convert to milliseconds for logs
                "client_ip": client_host,
            },
        )
        
        return response


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces API key authentication
    
    This middleware:
    - Checks for X-API-Key header on all requests
    - Validates the API key against configured value
    - Allows certain public paths without authentication
    - Returns 401 Unauthorized for invalid/missing keys
    
    Public paths (no authentication required):
    - /health, /health/*, /docs, /redoc, /openapi.json
    - Root path /
    
    All other paths require valid API key
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS: List[str] = [
        "/",
        "/health",
        "/health/detailed",
        "/health/ready",
        "/health/live",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check API key and process request
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response from route handler or 401 error
        """
        # Check if this is a public path
        if request.url.path in self.PUBLIC_PATHS:
            # Public path - no authentication required
            return await call_next(request)
        
        # Get API key from header
        # Header name: X-API-Key
        # Example: X-API-Key: your-secret-key-here
        api_key = request.headers.get("X-API-Key")
        
        # Check if API key was provided
        if not api_key:
            logger.warning(
                "Request missing API key",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "AUTHENTICATION_ERROR",
                    "message": "API key required. Provide X-API-Key header.",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # Validate API key
        if api_key != settings.API_KEY:
            logger.warning(
                "Invalid API key attempted",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "provided_key_prefix": api_key[:8] + "...",  # Only log first 8 chars
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "AUTHENTICATION_ERROR",
                    "message": "Invalid API key",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        # API key is valid - store it in request state for route handlers to access
        request.state.api_key = api_key
        
        # Log successful authentication
        logger.debug(
            "API key validated successfully",
            extra={
                "path": request.url.path,
                "method": request.method,
            },
        )
        
        # Process the request
        response = await call_next(request)
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that implements rate limiting
    
    Limits the number of requests per client based on:
    - Requests per minute (default: 60)
    - Requests per hour (default: 1000)
    
    Uses in-memory storage (can be upgraded to Redis for distributed systems)
    
    Rate limit is based on:
    - API key (if authenticated)
    - IP address (if not authenticated)
    
    Returns 429 Too Many Requests when limit exceeded
    Adds headers showing rate limit status:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining
    - X-RateLimit-Reset: When the limit resets (Unix timestamp)
    """
    
    # Storage for rate limit data
    # Format: {client_id: [(timestamp1, timestamp2, ...)]}
    _requests: Dict[str, List[float]] = defaultdict(list)
    
    def __init__(self, app):
        """Initialize rate limiter"""
        super().__init__(app)
        self.requests_per_minute = settings.RATE_LIMIT_PER_MINUTE  # From .env
        self.requests_per_hour = settings.RATE_LIMIT_PER_HOUR      # From .env
        self.enabled = settings.RATE_LIMIT_ENABLED                 # From .env
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get unique identifier for the client
        
        Priority:
        1. API key (if authenticated)
        2. IP address (fallback)
        
        Args:
            request: The incoming request
            
        Returns:
            Unique client identifier
        """
        # If authenticated, use API key
        api_key = getattr(request.state, "api_key", None)
        if api_key:
            return f"api_key:{api_key[:16]}"  # Use first 16 chars
        
        # Otherwise use IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _clean_old_requests(self, client_id: str, current_time: float) -> None:
        """
        Remove requests older than 1 hour
        
        Args:
            client_id: Client identifier
            current_time: Current timestamp
        """
        # Keep only requests from the last hour
        one_hour_ago = current_time - 3600  # 3600 seconds = 1 hour
        
        self._requests[client_id] = [
            timestamp 
            for timestamp in self._requests[client_id]
            if timestamp > one_hour_ago
        ]
    
    def _check_rate_limit(
        self, client_id: str, current_time: float
    ) -> Tuple[bool, int, int]:
        """
        Check if client has exceeded rate limit
        
        Args:
            client_id: Client identifier
            current_time: Current timestamp
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time)
            - is_allowed: True if request should be allowed
            - remaining_requests: How many requests remaining
            - reset_time: When the limit resets (Unix timestamp)
        """
        # Clean old requests first
        self._clean_old_requests(client_id, current_time)
        
        # Get all requests in the last minute and hour
        one_minute_ago = current_time - 60
        requests_last_minute = sum(
            1 for t in self._requests[client_id] if t > one_minute_ago
        )
        requests_last_hour = len(self._requests[client_id])
        
        # Check minute limit
        if requests_last_minute >= self.requests_per_minute:
            # Calculate when the minute limit resets
            oldest_in_minute = min(
                (t for t in self._requests[client_id] if t > one_minute_ago),
                default=current_time
            )
            reset_time = int(oldest_in_minute + 60)
            return False, 0, reset_time
        
        # Check hour limit
        if requests_last_hour >= self.requests_per_hour:
            # Calculate when the hour limit resets
            oldest_request = min(self._requests[client_id], default=current_time)
            reset_time = int(oldest_request + 3600)
            return False, 0, reset_time
        
        # Calculate remaining requests (use the most restrictive limit)
        remaining_minute = self.requests_per_minute - requests_last_minute
        remaining_hour = self.requests_per_hour - requests_last_hour
        remaining = min(remaining_minute, remaining_hour)
        
        # Calculate next reset time (1 minute from now)
        reset_time = int(current_time + 60)
        
        return True, remaining, reset_time
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit and process request
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response with rate limit headers or 429 error
        """
        # Skip rate limiting if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for public paths
        public_paths = ["/", "/health", "/health/detailed", "/health/ready", "/health/live"]
        if request.url.path in public_paths:
            return await call_next(request)
        
        # Get client ID
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Check rate limit
        is_allowed, remaining, reset_time = self._check_rate_limit(client_id, current_time)
        
        if not is_allowed:
            # Rate limit exceeded
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "client_id": client_id,
                    "path": request.url.path,
                    "method": request.method,
                    "reset_time": reset_time,
                },
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Try again after {reset_time}.",
                    "detail": {
                        "retry_after": reset_time - int(current_time),
                    },
                },
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(current_time)),
                },
            )
        
        # Record this request
        self._requests[client_id].append(current_time)
        
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)  # -1 for current request
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response


# Export all middleware classes
__all__ = [
    "PrometheusMiddleware",
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "APIKeyAuthMiddleware",
    "RateLimitMiddleware",
]