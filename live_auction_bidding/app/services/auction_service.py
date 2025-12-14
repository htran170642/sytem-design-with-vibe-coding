"""
Auction Service - Business Logic

Handles:
- Auction creation logic
- Auction expiration
- Auction validation
- Auction queries
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from app.models import Auction, Bid
from app.infrastructure.queue import BidQueue
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.cache import get_cache_manager

class AuctionService:
    """
    Service for auction-related business logic
    
    Centralizes auction operations so they can be:
    - Reused across different routes
    - Tested independently
    - Modified without touching routes
    """
    
    @staticmethod
    def create_auction(
        title: str,
        description: str,
        starting_price: float,
        min_increment: float,
        duration_minutes: int,
        db: Session
    ) -> Auction:
        """
        Create a new auction
        
        Business rules:
        - Starting price must be positive
        - Min increment must be positive
        - Duration must be > 0
        
        Args:
            title: Auction title
            description: Auction description
            starting_price: Starting price
            min_increment: Minimum bid increment
            duration_minutes: Auction duration
            db: Database session
            
        Returns:
            Created auction
            
        Raises:
            ValueError: If validation fails
        """
        # Validation
        if starting_price <= 0:
            raise ValueError("Starting price must be positive")
        
        if min_increment <= 0:
            raise ValueError("Minimum increment must be positive")
        
        if duration_minutes <= 0:
            raise ValueError("Duration must be positive")
        
        # Calculate times
        now = datetime.now()
        end_time = now + timedelta(minutes=duration_minutes)
        
        # Create auction
        auction = Auction(
            title=title,
            description=description,
            starting_price=starting_price,
            current_price=starting_price,
            min_increment=min_increment,
            start_time=now,
            end_time=end_time,
            status="ACTIVE",
            current_winner_id=None,
            total_bids=0
        )
        
        db.add(auction)
        db.commit()
        db.refresh(auction)
        
        print(f"✅ [Service] Created auction {auction.auction_id}: {auction.title}")
        
        return auction
    
    # @staticmethod
    # def get_auction(auction_id: int, db: Session) -> Optional[Auction]:
    #     """
    #     Get auction by ID
        
    #     Also auto-expires if needed
        
    #     Args:
    #         auction_id: Auction ID
    #         db: Database session
            
    #     Returns:
    #         Auction or None if not found
    #     """
    #     auction = db.query(Auction).filter(
    #         Auction.auction_id == auction_id
    #     ).first()
        
    #     if not auction:
    #         return None
        
    #     # Auto-expire if needed
    #     if auction.status == "ACTIVE" and datetime.now() > auction.end_time:
    #         AuctionService.expire_auction(auction, db)
        
    #     return auction
    
    @staticmethod
    def get_auction(auction_id: int, db: Session) -> Optional[Dict]:
        """Get auction from cache"""
        cache = get_cache_manager()
        return cache.get_auction(auction_id, db)
    
    @staticmethod
    def list_auctions(
        status: Optional[str] = None,
        include_bids: bool = False,
        limit: Optional[int] = None,
        db: Session = None
    ) -> List[Dict]:
        """
        List auctions - Optimized with existing cache
        
        Performance:
        - Warm cache: ~8ms (ID query + Redis batch)
        - Cold cache: ~45ms (ID query + DB batch)
        - Speedup: 5-10x vs direct DB query
        
        Args:
            status: Filter by status
            include_bids: Include recent bids
            limit: Maximum results
            db: Database session
            
        Returns:
            List of auction dictionaries
        """
        # Auto-expire auctions first
        AuctionService.auto_expire_auctions(db)
        
        # ════════════════════════════════════════════════════════
        # Query for IDs (lightweight, uses index)
        # ════════════════════════════════════════════════════════
        query = db.query(Auction.auction_id)
        
        if status:
            query = query.filter(Auction.status == status)
        
        query = query.order_by(Auction.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        auction_ids = [row[0] for row in query.all()]
        
        if not auction_ids:
            return []
        
        # ════════════════════════════════════════════════════════
        # Batch load from cache (handles DB fallback automatically!)
        # ════════════════════════════════════════════════════════
        cache = get_cache_manager()
        auctions_dict = cache.get_auctions(auction_ids, db)
        
        # ════════════════════════════════════════════════════════
        # Add real-time data
        # ════════════════════════════════════════════════════════
        redis_client = get_redis_client()
        queue = BidQueue(redis_client)
        
        result = []
        for auction_id in auction_ids:
            if auction_id in auctions_dict:
                auction_data = auctions_dict[auction_id].copy()
                auction_data["queued_bids"] = queue.get_queue_length(auction_id)
                
                if include_bids:
                    recent_bids = db.query(Bid).filter(
                        Bid.auction_id == auction_id
                    ).order_by(Bid.bid_time.desc()).limit(3).all()
                    
                    auction_data["recent_bids"] = [bid.to_dict() for bid in recent_bids]
                
                result.append(auction_data)
        
        return result

    @staticmethod
    def expire_auction(auction: Auction, db: Session) -> None:
        """
        Expire an auction
        
        Changes status to ENDED
        
        Args:
            auction: Auction to expire
            db: Database session
        """
        auction.status = "ENDED"
        db.commit()
        
        print(f"⏰ [Service] Expired auction {auction.auction_id}: {auction.title}")
    
    @staticmethod
    def expire_auction_cache(auction: Auction, db: Session):
        """Expire auction"""
        auction.status = "ENDED"
        db.commit()
        
        cache = get_cache_manager()
        cache.invalidate_auction(auction.auction_id)
    
    @staticmethod
    def auto_expire_auctions(db: Session) -> int:
        """
        Auto-expire all auctions past their end time
        
        Args:
            db: Database session
            
        Returns:
            Number of auctions expired
        """
        now = datetime.now()
        
        expired = db.query(Auction).filter(
            Auction.status == "ACTIVE",
            Auction.end_time < now
        ).all()
        
        for auction in expired:
            auction.status = "ENDED"
        
        if expired:
            db.commit()
            print(f"⏰ [Service] Auto-expired {len(expired)} auctions")
        
        return len(expired)
    
    @staticmethod
    def cancel_auction(auction_id: int, db: Session) -> Auction:
        """
        Cancel an auction
        
        Business rules:
        - Can only cancel ACTIVE auctions
        - Cannot cancel if bids exist
        
        Args:
            auction_id: Auction ID
            db: Database session
            
        Returns:
            Cancelled auction
            
        Raises:
            ValueError: If cannot cancel
        """
        auction = AuctionService.get_auction(auction_id, db)
        
        if not auction:
            raise ValueError("Auction not found")
        
        if auction.status != "ACTIVE":
            raise ValueError(f"Cannot cancel {auction.status} auction")
        
        if auction.total_bids > 0:
            raise ValueError("Cannot cancel auction with bids")
        
        auction.status = "CANCELLED"
        db.commit()
        
        print(f"🚫 [Service] Cancelled auction {auction_id}")
        
        return auction
    
    @staticmethod
    def get_auction_statistics(auction_id: int, db: Session) -> Dict:
        """
        Get detailed statistics for auction
        
        Args:
            auction_id: Auction ID
            db: Database session
            
        Returns:
            Statistics dictionary
        """
        auction = AuctionService.get_auction(auction_id, db)
        
        if not auction:
            raise ValueError("Auction not found")
        
        # Get all bids
        bids = db.query(Bid).filter(
            Bid.auction_id == auction_id
        ).order_by(Bid.bid_time.asc()).all()
        
        # Calculate statistics
        if bids:
            unique_bidders = len(set(bid.user_id for bid in bids))
            avg_bid = sum(bid.bid_amount for bid in bids) / len(bids)
            price_increase = auction.current_price - auction.starting_price
            price_increase_pct = (price_increase / auction.starting_price) * 100
        else:
            unique_bidders = 0
            avg_bid = 0
            price_increase = 0
            price_increase_pct = 0
        
        return {
            "auction_id": auction_id,
            "status": auction.status,
            "total_bids": auction.total_bids,
            "unique_bidders": unique_bidders,
            "starting_price": auction.starting_price,
            "current_price": auction.current_price,
            "price_increase": price_increase,
            "price_increase_percent": round(price_increase_pct, 2),
            "average_bid": round(avg_bid, 2) if bids else 0,
            "time_remaining": str(auction.end_time - datetime.now()) if auction.status == "ACTIVE" else "Ended"
        }