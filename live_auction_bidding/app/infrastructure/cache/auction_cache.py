"""
Auction Cache - High-frequency read optimization

Characteristics:
- Very high read frequency (listing, validation)
- Moderate write frequency (bids update price)
- Short TTL (60s) - data changes frequently
"""
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app.infrastructure.cache.base_cache import BaseCache
from app.models import Auction


class AuctionCache(BaseCache[Auction]):
    """
    Cache for auction entities
    
    Optimizations:
    - Batch loading for list pages
    - Short TTL for fresh data
    - Invalidation on bid placement
    """
    
    def _get_key_prefix(self) -> str:
        return "auction"
    
    def _fetch_from_db(self, auction_id: int, db: Session) -> Optional[Auction]:
        """Fetch single auction from database"""
        return db.query(Auction).filter(
            Auction.auction_id == auction_id
        ).first()
    
    def _fetch_many_from_db(self, auction_ids: List[int], db: Session) -> Dict[int, Auction]:
        """
        Optimized batch fetch using IN clause
        
        Much faster than N individual queries!
        """
        auctions = db.query(Auction).filter(
            Auction.auction_id.in_(auction_ids)
        ).all()
        
        # Convert to dict mapping id → auction
        return {
            auction.auction_id: auction
            for auction in auctions
        }
    
    def _serialize(self, auction: Auction) -> Dict:
        """Convert Auction to dict for caching"""
        return auction.to_dict()
    
    def _get_entity_id(self, entity: Auction) -> int:
        """Extract auction ID"""
        return entity.auction_id
    
    def warm_active(self, db: Session) -> int:
        """
        Warm cache with active auctions
        
        Called on server startup for fast initial loads.
        """
        active_auctions = db.query(Auction).filter(
            Auction.status == "ACTIVE"
        ).all()
        
        return self.warm(active_auctions)