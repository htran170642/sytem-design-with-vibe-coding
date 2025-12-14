"""
Redis client configuration and helper functions
"""
import redis
import json
from typing import Optional, Any
from functools import wraps
import time

# Redis connection
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True  # Automatically decode bytes to strings
)


def test_connection():
    """Test Redis connection"""
    try:
        redis_client.ping()
        print("✓ Redis connection successful")
        return True
    except redis.ConnectionError:
        print("✗ Redis connection failed")
        return False


# ============= CACHE DECORATOR =============

def cache_result(key_prefix: str, ttl: int = 300):
    """
    Cache decorator with TTL (Time To Live)
    
    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds (default 5 minutes)
    
    Example:
        @cache_result("messages", ttl=60)
        def get_messages(room_id, limit):
            # Expensive database query
            return messages
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            key_parts = [key_prefix]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[CACHE HIT] {cache_key}")
                return json.loads(cached)
            
            # Cache miss - execute function
            print(f"[CACHE MISS] {cache_key}")
            result = func(*args, **kwargs)
            
            # Store in cache with TTL
            redis_client.setex(cache_key, ttl, json.dumps(result))
            
            return result
        
        return wrapper
    return decorator


# ============= CACHE INVALIDATION =============

def invalidate_cache(pattern: str):
    """
    Delete all keys matching pattern
    
    Args:
        pattern: Redis key pattern (e.g., "messages:*")
    
    Example:
        invalidate_cache("messages:general:*")
    """
    keys = redis_client.keys(pattern)
    if keys:
        deleted = redis_client.delete(*keys)
        print(f"[CACHE INVALIDATE] Deleted {deleted} keys matching '{pattern}'")
        return deleted
    return 0


# ============= RATE LIMITING =============

def rate_limit(key_prefix: str, max_requests: int = 10, window: int = 60):
    """
    Rate limiting using Redis
    
    Args:
        key_prefix: Prefix for rate limit key
        max_requests: Maximum requests allowed
        window: Time window in seconds
    
    Returns:
        dict: {
            "allowed": bool,
            "remaining": int,
            "reset_at": int (timestamp)
        }
    
    Example:
        result = rate_limit("api:user:123", max_requests=100, window=3600)
        if not result["allowed"]:
            raise Exception("Rate limit exceeded")
    """
    def check_limit(identifier: str):
        rate_key = f"rate_limit:{key_prefix}:{identifier}"
        
        # Get current count
        current = redis_client.get(rate_key)
        
        if current is None:
            # First request - initialize counter
            redis_client.setex(rate_key, window, 1)
            return {
                "allowed": True,
                "remaining": max_requests - 1,
                "reset_at": int(time.time()) + window
            }
        
        current = int(current)
        print("Current count for {}: {}".format(rate_key, current))
        
        if current >= max_requests:
            # Rate limit exceeded
            ttl = redis_client.ttl(rate_key)
            return {
                "allowed": False,
                "remaining": 0,
                "reset_at": int(time.time()) + ttl
            }
        
        # Increment counter
        redis_client.incr(rate_key)
        ttl = redis_client.ttl(rate_key)
        
        return {
            "allowed": True,
            "remaining": max_requests - current - 1,
            "reset_at": int(time.time()) + ttl
        }
    
    return check_limit


# ============= HELPER FUNCTIONS =============

def set_json(key: str, value: Any, ttl: Optional[int] = None):
    """Store JSON data in Redis"""
    if ttl:
        redis_client.setex(key, ttl, json.dumps(value))
    else:
        redis_client.set(key, json.dumps(value))


def get_json(key: str) -> Optional[Any]:
    """Get JSON data from Redis"""
    data = redis_client.get(key)
    return json.loads(data) if data else None


def get_stats():
    """Get Redis statistics"""
    info = redis_client.info()
    return {
        "version": info.get("redis_version"),
        "used_memory": info.get("used_memory_human"),
        "connected_clients": info.get("connected_clients"),
        "total_commands": info.get("total_commands_processed"),
        "keyspace": redis_client.dbsize()
    }


def clear_all():
    """Clear all data from Redis (use with caution!)"""
    redis_client.flushdb()
    print("✓ Redis database cleared")


class RateLimitExceeded(Exception):
    """Custom exception for rate limit violations"""
    def __init__(self, message, retry_after):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


def rate_limit_sliding_window(
    key_prefix: str,
    identifier: str,
    max_requests: int = 10,
    window: int = 60
):
    """
    Advanced rate limiting using sliding window algorithm
    
    Args:
        key_prefix: Prefix for rate limit key (e.g., 'api', 'message')
        identifier: User identifier (user_id, IP address, etc.)
        max_requests: Maximum requests allowed in window
        window: Time window in seconds
    
    Returns:
        dict: {
            "allowed": bool,
            "remaining": int,
            "reset_at": int (Unix timestamp),
            "retry_after": int (seconds until can retry)
        }
    
    Raises:
        RateLimitExceeded: When limit is exceeded
    """
    import time
    
    rate_key = f"rate_limit:{key_prefix}:{identifier}"
    now = time.time()
    window_start = now - window
    
    # Use Redis pipeline for atomic operations
    pipe = redis_client.pipeline()
    
    # Remove old entries outside the window
    pipe.zremrangebyscore(rate_key, 0, window_start)
    
    # Count requests in current window
    pipe.zcard(rate_key)
    
    # Add current request
    pipe.zadd(rate_key, {now: now})
    
    # Set expiry
    pipe.expire(rate_key, window)
    
    # Execute pipeline
    results = pipe.execute()
    
    # Get count (before adding current request)
    request_count = results[1]
    
    # Calculate remaining and reset time
    remaining = max(0, max_requests - request_count - 1)
    reset_at = int(now + window)
    
    if request_count >= max_requests:
        # Get oldest request in window
        oldest = redis_client.zrange(rate_key, 0, 0, withscores=True)
        if oldest:
            retry_after = int(oldest[0][1] + window - now)
        else:
            retry_after = window
        
        # Remove the request we just added (we're rejecting it)
        redis_client.zrem(rate_key, now)
        
        return {
            "allowed": False,
            "remaining": 0,
            "reset_at": reset_at,
            "retry_after": retry_after
        }
    
    return {
        "allowed": True,
        "remaining": remaining,
        "reset_at": reset_at,
        "retry_after": 0
    }


def check_rate_limit(
    key_prefix: str,
    identifier: str,
    max_requests: int = 10,
    window: int = 60
):
    """
    Check rate limit and raise exception if exceeded
    
    Usage:
        check_rate_limit('message', user_id, max_requests=10, window=60)
    
    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    result = rate_limit_sliding_window(key_prefix, identifier, max_requests, window)
    
    if not result['allowed']:
        raise RateLimitExceeded(
            message=f"Rate limit exceeded. Try again in {result['retry_after']} seconds.",
            retry_after=result['retry_after']
        )
    
    return result


# ============= RATE LIMIT TIERS =============

RATE_LIMITS = {
    'messages': {
        'max_requests': 10,
        'window': 60,  # 10 messages per minute
        'description': 'Message posting limit'
    },
    'api': {
        'max_requests': 100,
        'window': 60,  # 100 API calls per minute
        'description': 'General API limit'
    },
    'login': {
        'max_requests': 5,
        'window': 300,  # 5 login attempts per 5 minutes
        'description': 'Login attempt limit'
    },
    'register': {
        'max_requests': 3,
        'window': 3600,  # 3 registrations per hour
        'description': 'User registration limit'
    }
}


def get_rate_limit_config(limit_type: str):
    """Get rate limit configuration for a specific type"""
    return RATE_LIMITS.get(limit_type, RATE_LIMITS['api'])


# ============= RATE LIMIT STATS =============

def get_rate_limit_stats(key_prefix: str, identifier: str):
    """
    Get current rate limit statistics for a user
    
    Returns:
        dict: Current usage statistics
    """
    import time
    
    rate_key = f"rate_limit:{key_prefix}:{identifier}"
    now = time.time()
    
    # Get all requests in the current window
    config = get_rate_limit_config(key_prefix)
    window = config['window']
    window_start = now - window
    
    requests = redis_client.zrangebyscore(rate_key, window_start, now, withscores=True)
    
    return {
        "current_count": len(requests),
        "max_requests": config['max_requests'],
        "window": window,
        "remaining": max(0, config['max_requests'] - len(requests)),
        "requests": [
            {
                "timestamp": int(score),
                "age_seconds": int(now - score)
            }
            for _, score in requests
        ]
    }


def reset_rate_limit(key_prefix: str, identifier: str):
    """
    Reset rate limit for a specific user (admin function)
    
    Usage:
        reset_rate_limit('message', 'user123')
    """
    rate_key = f"rate_limit:{key_prefix}:{identifier}"
    deleted = redis_client.delete(rate_key)
    
    if deleted:
        print(f"✓ Rate limit reset for {key_prefix}:{identifier}")
    else:
        print(f"ℹ️  No rate limit found for {key_prefix}:{identifier}")
    
    return deleted > 0

if __name__ == "__main__":
    # Test connection
    test_connection()
    
    # Show stats
    stats = get_stats()
    print("\nRedis Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")