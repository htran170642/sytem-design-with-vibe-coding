"""Rate limiting for the ingestion service.

This module provides token bucket-based rate limiting to prevent
API abuse and ensure fair usage across different API keys.
"""
import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import HTTPException, Request, status

from observability.common.logger import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(HTTPException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


class TokenBucket:
    """Token bucket algorithm for rate limiting.
    
    The token bucket algorithm works like this:
    1. Bucket starts full with N tokens
    2. Each request consumes 1 token
    3. Tokens refill at a constant rate (e.g., 10 per second)
    4. If no tokens available, request is rejected
    
    Example:
        - Capacity: 100 tokens
        - Refill rate: 10 tokens/second
        - Allows bursts up to 100 requests
        - Sustained rate: 10 requests/second
    
    This is better than simple "requests per minute" because:
    - Allows bursts (good user experience)
    - Prevents sustained abuse
    - Smoother rate limiting
    """

    def __init__(
        self,
        capacity: int = 100,
        refill_rate: float = 10.0,  # tokens per second
    ):
        """Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens (burst size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Calculate tokens to add
        tokens_to_add = elapsed * self.refill_rate
        
        # Add tokens, but don't exceed capacity
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_available_tokens(self) -> int:
        """Get current number of available tokens.
        
        Returns:
            Number of available tokens
        """
        self._refill()
        return int(self.tokens)

    def get_wait_time(self, tokens: int = 1) -> float:
        """Calculate how long to wait until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time in seconds to wait
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Rate limiter using token bucket algorithm.
    
    Maintains separate token buckets for each API key.
    
    Example usage:
        ```python
        limiter = RateLimiter(requests_per_second=10, burst_size=100)
        
        # In your endpoint:
        if not limiter.check_limit(api_key):
            raise RateLimitExceeded()
        ```
    """

    def __init__(
        self,
        requests_per_second: float = 100.0,
        burst_size: int = 1000,
    ):
        """Initialize rate limiter.
        
        Args:
            requests_per_second: Sustained rate limit
            burst_size: Maximum burst size
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        
        # Store token buckets per API key
        self.buckets: Dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=self.burst_size,
                refill_rate=self.requests_per_second,
            )
        )
        
        logger.info(
            "Rate limiter initialized",
            requests_per_second=requests_per_second,
            burst_size=burst_size,
        )

    def check_limit(self, key: str, tokens: int = 1) -> bool:
        """Check if request is within rate limit.
        
        Args:
            key: Identifier (usually API key)
            tokens: Number of tokens to consume (default: 1)
            
        Returns:
            True if within limit, False if limit exceeded
        """
        bucket = self.buckets[key]
        allowed = bucket.consume(tokens)
        
        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                key_prefix=key[:8] if len(key) >= 8 else "***",
                available_tokens=bucket.get_available_tokens(),
                wait_time=bucket.get_wait_time(tokens),
            )
        
        return allowed

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for a key.
        
        Args:
            key: Identifier (usually API key)
            
        Returns:
            Number of remaining requests
        """
        bucket = self.buckets[key]
        return bucket.get_available_tokens()

    def get_retry_after(self, key: str, tokens: int = 1) -> int:
        """Get seconds until next request is allowed.
        
        Args:
            key: Identifier (usually API key)
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if can proceed now)
        """
        bucket = self.buckets[key]
        return int(bucket.get_wait_time(tokens)) + 1  # Add 1 for safety

    def reset(self, key: str) -> None:
        """Reset rate limit for a key.
        
        Useful for testing or administrative actions.
        
        Args:
            key: Identifier to reset
        """
        if key in self.buckets:
            del self.buckets[key]
            logger.info("Rate limit reset", key_prefix=key[:8])

    def get_stats(self, key: str) -> dict:
        """Get statistics for a key.
        
        Args:
            key: Identifier to check
            
        Returns:
            Dictionary with stats
        """
        if key not in self.buckets:
            return {
                "available_tokens": self.burst_size,
                "capacity": self.burst_size,
                "refill_rate": self.requests_per_second,
            }
        
        bucket = self.buckets[key]
        return {
            "available_tokens": bucket.get_available_tokens(),
            "capacity": bucket.capacity,
            "refill_rate": bucket.refill_rate,
        }


# Global rate limiter instance
# In production, you might use Redis for distributed rate limiting
rate_limiter = RateLimiter(
    requests_per_second=100.0,  # 100 requests per second sustained
    burst_size=1000,  # Allow bursts up to 1000 requests
)


async def check_rate_limit(request: Request, api_key: str) -> None:
    """FastAPI dependency to check rate limits.
    
    This is used as a dependency in FastAPI endpoints.
    
    Args:
        request: FastAPI request object
        api_key: API key from authentication
        
    Raises:
        RateLimitExceeded: If rate limit is exceeded
        
    Example:
        ```python
        @app.post("/logs")
        async def ingest_logs(
            batch: LogBatch,
            api_key: str = Depends(verify_api_key),
            _: None = Depends(check_rate_limit)  # Rate limit check
        ):
            # This only runs if rate limit OK
            pass
        ```
    """
    # Use API key as the rate limit key
    # In production, you might combine with IP address or user ID
    limit_key = api_key
    
    if not rate_limiter.check_limit(limit_key):
        retry_after = rate_limiter.get_retry_after(limit_key)
        
        logger.warning(
            "Rate limit exceeded for request",
            path=request.url.path,
            key_prefix=api_key[:8] if len(api_key) >= 8 else "***",
            retry_after=retry_after,
        )
        
        raise RateLimitExceeded(retry_after=retry_after)
    
    # Log successful rate limit check (debug only)
    remaining = rate_limiter.get_remaining(limit_key)
    logger.debug(
        "Rate limit check passed",
        remaining_tokens=remaining,
    )


class SlidingWindowRateLimiter:
    """Alternative: Sliding window rate limiter.
    
    This is simpler but less flexible than token bucket.
    Good for simple "N requests per minute" limits.
    
    Example:
        limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)
        # Allows 100 requests per 60-second window
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize sliding window limiter.
        
        Args:
            max_requests: Maximum requests in window
            window_seconds: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Store timestamps per key
        self.requests: Dict[str, list] = defaultdict(list)

    def check_limit(self, key: str) -> bool:
        """Check if request is within limit.
        
        Args:
            key: Identifier (usually API key)
            
        Returns:
            True if within limit, False otherwise
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Get requests for this key
        requests = self.requests[key]
        
        # Remove old requests outside window
        requests[:] = [ts for ts in requests if ts > window_start]
        
        # Check if limit exceeded
        if len(requests) >= self.max_requests:
            return False
        
        # Add current request
        requests.append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests in current window.
        
        Args:
            key: Identifier
            
        Returns:
            Number of remaining requests
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        requests = self.requests[key]
        requests[:] = [ts for ts in requests if ts > window_start]
        
        return max(0, self.max_requests - len(requests))