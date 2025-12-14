"""
Cache Service

Provides high-level cache operations for the application.

Benefits:
- Single point of cache access
- Easy to test (can mock)
- Hides infrastructure details
- Clean business logic
"""
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.cache import get_cache
from app.models import Auction


class CacheService:
    """
    Service for cache operations
    
    This is a facade/wrapper around the infrastructure cache layer.
    Business logic should use this, not direct cache access.
    
    Design Pattern: Facade Pattern
    - Simplifies complex subsystem (Redis + Cache)
    - Provides business-oriented interface
    - Hides implementation details
    """
    
    def __init__(self):
        """Initialize cache service"""
        self.redis_client = get_redis_client()
        self.cache = get_cache(self.redis_client)
    
    # ========================================================================
    # AUCTION CACHE OPERATIONS
    # ========================================================================
    
    def get_auction(self, auction_id: int, db: Session) -> Optional[Dict]:
        """
        Get auction data from cache
        
        Business-level method for getting cached auction data.
        Used for fast validation and lookups.
        
        Args:
            auction_id: Auction ID
            db: Database session
            
        Returns:
            Auction data dict or None
            
        Example:
            >>> cache_service = CacheService()
            >>> auction_data = cache_service.get_auction(123, db)
            >>> if auction_data:
            >>>     print(f"Price: ${auction_data['current_price']}")
        """
        return self.cache.get(auction_id, db)
    
    def invalidate_auction(self, auction_id: int):
        """
        Invalidate auction cache
        
        Call this when auction data changes:
        - Bid placed
        - Status changed
        - Any update
        
        Args:
            auction_id: Auction ID
            
        Example:
            >>> cache_service = CacheService()
            >>> # After placing bid:
            >>> cache_service.invalidate_auction(123)
        """
        self.cache.invalidate(auction_id)
        print(f"🗑️  [CacheService] Invalidated auction {auction_id}")
    
    def invalidate_multiple_auctions(self, auction_ids: List[int]):
        """
        Invalidate multiple auctions at once
        
        Useful for batch operations.
        
        Args:
            auction_ids: List of auction IDs
            
        Example:
            >>> cache_service.invalidate_multiple_auctions([1, 2, 3])
        """
        for auction_id in auction_ids:
            self.cache.invalidate(auction_id)
        
        print(f"🗑️  [CacheService] Invalidated {len(auction_ids)} auctions")
    
    def warm_auctions(self, db: Session, status: str = "ACTIVE") -> int:
        """
        Warm cache with auctions
        
        Pre-loads auctions into cache for fast access.
        
        Args:
            db: Database session
            status: Auction status to cache
            
        Returns:
            Number of auctions cached
            
        Example:
            >>> cache_service = CacheService()
            >>> count = cache_service.warm_auctions(db)
            >>> print(f"Warmed {count} auctions")
        """
        return self.cache.warm(db, status=status)
    
    def clear_all_auctions(self):
        """
        Clear all auction caches
        
        ⚠️ USE WITH CAUTION!
        
        Example:
            >>> cache_service.clear_all_auctions()
        """
        self.cache.clear_all()
        print(f"🗑️  [CacheService] Cleared all auction caches")
    
    # ========================================================================
    # STATISTICS & MONITORING
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """
        Get cache statistics
        
        Returns:
            Dict with cache metrics
            
        Example:
            >>> stats = cache_service.get_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
        """
        return self.cache.get_stats()
    
    def get_hit_rate(self) -> float:
        """
        Get current cache hit rate
        
        Returns:
            Hit rate (0.0 to 1.0)
        """
        return self.cache.get_hit_rate()
    
    def get_detailed_stats(self) -> Dict:
        """
        Get detailed cache statistics
        
        Returns:
            Detailed metrics including performance analysis
        """
        stats = self.cache.get_stats()
        hit_rate = stats['hit_rate']
        
        # Performance analysis
        if hit_rate >= 0.99:
            performance = "Excellent"
            recommendation = "Cache is performing optimally"
        elif hit_rate >= 0.90:
            performance = "Good"
            recommendation = "Cache is performing well"
        elif hit_rate >= 0.75:
            performance = "Fair"
            recommendation = "Consider increasing TTL or warming cache more frequently"
        else:
            performance = "Poor"
            recommendation = "Investigate cache misses and consider cache strategy"
        
        return {
            **stats,
            "performance": performance,
            "recommendation": recommendation,
            "total_requests": stats['hits'] + stats['misses']
        }
    
    # ========================================================================
    # HEALTH CHECKS
    # ========================================================================
    
    def health_check(self) -> Dict:
        """
        Check cache health
        
        Returns:
            Health status
        """
        try:
            # Test Redis connection
            self.redis_client.ping()
            
            stats = self.get_stats()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "hit_rate": stats['hit_rate'],
                "total_hits": stats['hits'],
                "total_misses": stats['misses']
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e)
            }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_cache_service_instance = None

def get_cache_service() -> CacheService:
    """
    Get singleton cache service instance
    
    Returns:
        CacheService instance
        
    Example:
        >>> from app.services.cache_service import get_cache_service
        >>> cache_service = get_cache_service()
        >>> auction_data = cache_service.get_auction(123, db)
    """
    global _cache_service_instance
    
    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
    
    return _cache_service_instance