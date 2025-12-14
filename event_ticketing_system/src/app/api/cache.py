"""
Cache management and monitoring API
"""
from fastapi import APIRouter, HTTPException
from app.core.redis import redis_client
from typing import Dict, Any, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    Get Redis cache statistics
    
    Returns:
    - Total keys
    - Memory usage
    - Hit/miss ratio
    - Uptime
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        # Get Redis INFO
        info = await redis_client.redis.info()
        
        # Get all keys count
        keys_count = await redis_client.redis.dbsize()
        
        # Get keys by pattern
        event_keys = 0
        seat_keys = 0
        availability_keys = 0
        
        async for key in redis_client.redis.scan_iter(match="event:*"):
            if ":seats" in key:
                seat_keys += 1
            elif ":availability" in key:
                availability_keys += 1
            else:
                event_keys += 1
        
        return {
            "status": "connected",
            "total_keys": keys_count,
            "keys_breakdown": {
                "events": event_keys,
                "seats": seat_keys,
                "availability": availability_keys
            },
            "memory": {
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio")
            },
            "stats": {
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            },
            "uptime_seconds": info.get("uptime_in_seconds"),
            "uptime_days": round(info.get("uptime_in_seconds", 0) / 86400, 2)
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/keys")
async def list_cache_keys(pattern: str = "*", limit: int = 100) -> Dict[str, Any]:
    """
    List cache keys matching pattern
    
    Args:
    - pattern: Redis key pattern (default: *)
    - limit: Max number of keys to return (default: 100)
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        keys = []
        count = 0
        
        async for key in redis_client.redis.scan_iter(match=pattern):
            if count >= limit:
                break
            
            # Get TTL
            ttl = await redis_client.redis.ttl(key)
            
            # Get type
            key_type = await redis_client.redis.type(key)
            
            keys.append({
                "key": key,
                "type": key_type,
                "ttl_seconds": ttl if ttl > 0 else None,
                "expires_in": format_ttl(ttl) if ttl > 0 else "no expiry"
            })
            count += 1
        
        return {
            "pattern": pattern,
            "count": len(keys),
            "limit": limit,
            "keys": keys
        }
    except Exception as e:
        logger.error(f"Error listing cache keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/key/{key}")
async def get_cache_key(key: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific cache key
    
    Args:
    - key: Redis key to inspect
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        # Check if key exists
        exists = await redis_client.redis.exists(key)
        if not exists:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
        
        # Get value
        value = await redis_client.redis.get(key)
        
        # Get TTL
        ttl = await redis_client.redis.ttl(key)
        
        # Get type
        key_type = await redis_client.redis.type(key)
        
        # Get memory usage (if available)
        try:
            memory = await redis_client.redis.memory_usage(key)
        except:
            memory = None
        
        return {
            "key": key,
            "type": key_type,
            "ttl_seconds": ttl if ttl > 0 else None,
            "expires_in": format_ttl(ttl) if ttl > 0 else "no expiry",
            "memory_bytes": memory,
            "memory_human": f"{memory / 1024:.2f} KB" if memory else None,
            "value_preview": value[:200] + "..." if len(value) > 200 else value
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/key/{key}")
async def delete_cache_key(key: str) -> Dict[str, str]:
    """
    Delete a specific cache key
    
    Args:
    - key: Redis key to delete
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        deleted = await redis_client.redis.delete(key)
        if deleted:
            return {"message": f"Key '{key}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cache key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/pattern/{pattern}")
async def delete_cache_pattern(pattern: str) -> Dict[str, Any]:
    """
    Delete all cache keys matching pattern
    
    Args:
    - pattern: Redis key pattern (e.g., "event:*:seats")
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        deleted_count = await redis_client.delete_pattern(pattern)
        return {
            "pattern": pattern,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} keys matching pattern '{pattern}'"
        }
    except Exception as e:
        logger.error(f"Error deleting cache pattern: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/flush")
async def flush_cache() -> Dict[str, str]:
    """
    ⚠️ DANGER: Flush all cache data
    
    This will delete ALL keys in the current Redis database
    """
    if not redis_client.redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        await redis_client.redis.flushdb()
        return {"message": "Cache flushed successfully"}
    except Exception as e:
        logger.error(f"Error flushing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions
def calculate_hit_rate(hits: int, misses: int) -> Optional[float]:
    """Calculate cache hit rate percentage"""
    total = hits + misses
    if total == 0:
        return None
    return round((hits / total) * 100, 2)


def format_ttl(seconds: int) -> str:
    """Format TTL in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
