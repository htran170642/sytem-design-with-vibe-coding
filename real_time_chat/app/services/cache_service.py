"""
Cache service - Redis caching operations
"""
from typing import Optional, Any
import json
import redis
from functools import wraps

from app.config import settings


class CacheService:
    """Service for caching operations"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern
        
        Args:
            pattern: Key pattern (e.g., "messages:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0
    
    def invalidate_messages_cache(self, room_id: str):
        """Invalidate all message cache for a room"""
        pattern = f"messages:{room_id}:*"
        deleted = self.delete_pattern(pattern)
        print(f"Invalidated {deleted} cache entries for room {room_id}")
    
    def invalidate_dm_cache(self, user1_id: int, user2_id: int):
        """Invalidate direct message cache"""
        min_id = min(user1_id, user2_id)
        max_id = max(user1_id, user2_id)
        pattern = f"dm:{min_id}:{max_id}:*"
        deleted = self.delete_pattern(pattern)
        print(f"Invalidated {deleted} DM cache entries")
    
    def get_stats(self) -> dict:
        """Get Redis statistics"""
        try:
            info = self.redis_client.info()
            return {
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            return {"error": str(e)}


# Global cache service instance
cache_service = CacheService()