"""
Cache Manager - Centralized cache coordination

Single entry point for all cache operations.
Coordinates auction, bid, and future cache types.
"""
import redis
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.cache.auction_cache import AuctionCache
from app.infrastructure.cache.bid_cache import BidCache


class CacheManager:
    """
    Centralized cache manager
    
    Benefits:
    - Single point of cache access
    - Coordinates multiple cache types
    - Unified statistics
    - Easy to test
    """
    
    def __init__(self):
        """Initialize all caches"""
        settings = get_settings()
        self.redis_client = get_redis_client()
        
        # Initialize specific caches
        self.auctions = AuctionCache(
            redis_client=self.redis_client,
            ttl=settings.CACHE_TTL  # 60 seconds
        )
        
        self.bids = BidCache(
            redis_client=self.redis_client,
            ttl=300  # 5 minutes (bids don't change)
        )
    
    # ========================================================================
    # AUCTION OPERATIONS
    # ========================================================================
    
    def get_auction(self, auction_id: int, db: Session) -> Optional[Dict]:
        """Get auction from cache"""
        return self.auctions.get(auction_id, db)
    
    def get_auctions(self, auction_ids: List[int], db: Session) -> Dict[int, Dict]:
        """Get multiple auctions (batch)"""
        return self.auctions.get_many(auction_ids, db)
    
    def invalidate_auction(self, auction_id: int):
        """Invalidate auction cache"""
        self.auctions.invalidate(auction_id)
    
    def warm(self, db: Session) -> int:
        """Warm auction cache"""
        return self.auctions.warm_active(db)
    
    # ========================================================================
    # BID OPERATIONS
    # ========================================================================
    
    def get_bid(self, bid_id: int, db: Session) -> Optional[Dict]:
        """Get bid from cache"""
        return self.bids.get(bid_id, db)
    
    def get_bids(self, bid_ids: List[int], db: Session) -> Dict[int, Dict]:
        """Get multiple bids (batch)"""
        return self.bids.get_many(bid_ids, db)
    
    def get_recent_bids(
        self,
        auction_id: int,
        limit: int,
        db: Session
    ) -> List[Dict]:
        """Get recent bids for auction"""
        return self.bids.get_recent_by_auction(auction_id, limit, db)
    
    # ========================================================================
    # COMBINED OPERATIONS
    # ========================================================================
    
    def invalidate_auction_with_bids(self, auction_id: int, db: Session):
        """
        Invalidate auction and its recent bids
        
        Called after bid placement.
        """
        # Invalidate auction
        self.auctions.invalidate(auction_id)
        
        # Invalidate recent bids list cache
        list_key = f"auction_bids:{auction_id}:*"
        keys = self.redis_client.keys(list_key)
        if keys:
            self.redis_client.delete(*keys)
    
    # ========================================================================
    # STATISTICS & MONITORING
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """Get combined statistics"""
        return {
            "auctions": self.auctions.get_stats(),
            "bids": self.bids.get_stats(),
            "overall_hit_rate": self._calculate_overall_hit_rate()
        }
    
    def _calculate_overall_hit_rate(self) -> float:
        """Calculate overall hit rate across all caches"""
        total_hits = self.auctions.hits + self.bids.hits
        total_misses = self.auctions.misses + self.bids.misses
        total = total_hits + total_misses
        
        if total == 0:
            return 0.0
        
        return total_hits / total
    
    def health_check(self) -> Dict:
        """Check cache health"""
        try:
            self.redis_client.ping()
            stats = self.get_stats()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "stats": stats
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e)
            }
    
    def clear_all(self):
        """Clear all caches"""
        self.auctions.clear_all()
        self.bids.clear_all()


# ============================================================================
# SINGLETON
# ============================================================================
_cache_manager_instance = None

def get_cache_manager() -> CacheManager:
    """
    Get singleton cache manager
    
    Usage:
        from app.infrastructure.cache import get_cache_manager
        
        cache = get_cache_manager()
        auction = cache.get_auction(123, db)
        bids = cache.get_recent_bids(123, 10, db)
    """
    global _cache_manager_instance
    
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
    
    return _cache_manager_instance