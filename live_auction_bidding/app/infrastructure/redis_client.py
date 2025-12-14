"""
Redis Connection
"""
import redis
from app.core.config import get_settings

settings = get_settings()

_redis_client = None


def get_redis_client() -> redis.Redis:
    """Get Redis client (singleton)"""
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    
    return _redis_client


def test_redis_connection() -> bool:
    """Test Redis connection"""
    try:
        client = get_redis_client()
        client.ping()
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False