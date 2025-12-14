"""
Cache service for managing Redis cache
"""
from typing import Optional, List, Dict, Any
from app.core.redis import redis_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing cache keys and invalidation"""
    
    # Cache key patterns
    EVENT_KEY = "event:{event_id}"
    EVENT_SEATS_KEY = "event:{event_id}:seats"
    EVENT_AVAILABILITY_KEY = "event:{event_id}:availability"
    EVENTS_LIST_KEY = "events:list:page:{page}:size:{size}:city:{city}:category:{category}"
    
    @staticmethod
    async def get_event(event_id: int) -> Optional[Dict[str, Any]]:
        """Get cached event"""
        key = CacheService.EVENT_KEY.format(event_id=event_id)
        return await redis_client.get(key)
    
    @staticmethod
    async def set_event(event_id: int, data: Dict[str, Any]) -> bool:
        """Cache event data"""
        key = CacheService.EVENT_KEY.format(event_id=event_id)
        return await redis_client.set(key, data, ttl=settings.REDIS_CACHE_TTL)
    
    @staticmethod
    async def get_event_seats(event_id: int) -> Optional[Dict[str, Any]]:
        """Get cached seat map"""
        key = CacheService.EVENT_SEATS_KEY.format(event_id=event_id)
        cached = await redis_client.get(key)
        if cached:
            logger.info(f"✅ Cache HIT: {key}")
        else:
            logger.info(f"❌ Cache MISS: {key}")
        return cached
    
    @staticmethod
    async def set_event_seats(event_id: int, data: Dict[str, Any]) -> bool:
        """Cache seat map (short TTL due to high volatility)"""
        key = CacheService.EVENT_SEATS_KEY.format(event_id=event_id)
        success = await redis_client.set(key, data, ttl=settings.REDIS_SEATS_TTL)
        if success:
            logger.info(f"💾 Cached: {key} (TTL: {settings.REDIS_SEATS_TTL}s)")
        return success
    
    @staticmethod
    async def invalidate_event(event_id: int) -> bool:
        """Invalidate all cache for an event"""
        keys_to_delete = [
            CacheService.EVENT_KEY.format(event_id=event_id),
            CacheService.EVENT_SEATS_KEY.format(event_id=event_id),
            CacheService.EVENT_AVAILABILITY_KEY.format(event_id=event_id),
        ]
        logger.info(f"🗑️ Invalidating cache for event {event_id}")
        return await redis_client.delete(*keys_to_delete)
    
    @staticmethod
    async def invalidate_event_seats(event_id: int) -> bool:
        """Invalidate only seat-related cache"""
        keys_to_delete = [
            CacheService.EVENT_SEATS_KEY.format(event_id=event_id),
            CacheService.EVENT_AVAILABILITY_KEY.format(event_id=event_id),
        ]
        logger.info(f"🗑️ Invalidating seat cache for event {event_id}")
        return await redis_client.delete(*keys_to_delete)
    
    @staticmethod
    async def get_event_availability(event_id: int) -> Optional[Dict[str, Any]]:
        """Get cached availability"""
        key = CacheService.EVENT_AVAILABILITY_KEY.format(event_id=event_id)
        return await redis_client.get(key)
    
    @staticmethod
    async def set_event_availability(event_id: int, data: Dict[str, Any]) -> bool:
        """Cache availability data"""
        key = CacheService.EVENT_AVAILABILITY_KEY.format(event_id=event_id)
        return await redis_client.set(key, data, ttl=settings.REDIS_SEATS_TTL)
