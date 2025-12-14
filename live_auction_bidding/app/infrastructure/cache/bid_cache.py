"""
Bid Cache - Historical data optimization

Characteristics:
- Medium read frequency (viewing bid history)
- Write-once (bids are immutable)
- Longer TTL (300s) - data never changes
"""
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app.infrastructure.cache.base_cache import BaseCache
from app.models import Bid
import json

class BidCache(BaseCache[Bid]):
    """
    Cache for bid entities
    
    Optimizations:
    - Longer TTL (bids don't change)
    - Batch loading for history pages
    - No invalidation needed (immutable)
    """
    
    def _get_key_prefix(self) -> str:
        return "bid"
    
    def _fetch_from_db(self, bid_id: int, db: Session) -> Optional[Bid]:
        """Fetch single bid from database"""
        return db.query(Bid).filter(
            Bid.bid_id == bid_id
        ).first()
    
    def _fetch_many_from_db(self, bid_ids: List[int], db: Session) -> Dict[int, Bid]:
        """Optimized batch fetch"""
        bids = db.query(Bid).filter(
            Bid.bid_id.in_(bid_ids)
        ).all()
        
        return {bid.bid_id: bid for bid in bids}
    
    def _serialize(self, bid: Bid) -> Dict:
        """Convert Bid to dict for caching"""
        return bid.to_dict()
    
    def _get_entity_id(self, entity: Bid) -> int:
        """Extract bid ID"""
        return entity.bid_id
    
    def get_recent_by_auction(
        self,
        auction_id: int,
        limit: int,
        db: Session
    ) -> List[Dict]:
        """
        Get recent bids for an auction (with caching)
        
        Caches the list of bid IDs, then loads individual bids.
        """
        # Cache key for the list
        list_key = f"auction_bids:{auction_id}:{limit}"
        
        # Try to get cached list of bid IDs
        cached_list = self.redis.get(list_key)
        
        if cached_list:
            # Cache hit - load individual bids
            bid_ids = json.loads(cached_list)
            bid_data = self.get_many(bid_ids, db)
            
            # Return in order
            return [bid_data[bid_id] for bid_id in bid_ids if bid_id in bid_data]
        
        # Cache miss - query database
        bids = db.query(Bid).filter(
            Bid.auction_id == auction_id
        ).order_by(Bid.bid_time.desc()).limit(limit).all()
        
        # Cache the list of IDs
        bid_ids = [bid.bid_id for bid in bids]
        self.redis.setex(list_key, 60, json.dumps(bid_ids))  # Short TTL
        
        # Cache individual bids
        for bid in bids:
            self.set(bid.bid_id, bid)
        
        return [bid.to_dict() for bid in bids]