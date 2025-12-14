"""
Bid Service - Business Logic

Handles:
- Bid validation
- Bid placement logic
- Bid history
- Bid statistics
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime

from app.models import Auction, Bid
from app.infrastructure.queue import BidQueue
from app.infrastructure.cache import get_cache_manager  # ← ADD THIS

from app.infrastructure.redis_client import get_redis_client


class BidService:
    """
    Service for bid-related business logic
    
    Centralizes bid operations
    """
    
    @staticmethod
    def validate_bid(
        auction_id: int,
        user_id: int,
        bid_amount: float,
        db: Session
    ) -> Dict:
        """
        Validate bid before queuing
        
        Checks:
        1. Auction exists
        2. Auction is active
        3. Auction not expired
        4. Bid amount is sufficient (from cache)
        
        Args:
            auction_id: Auction ID
            user_id: User ID
            bid_amount: Bid amount
            db: Database session
            
        Returns:
            Validation result with auction data
            
        Raises:
            ValueError: If validation fails
        """
        cache = get_cache_manager()
        auction_data = cache.get_auction(auction_id, db)
        
        if not auction_data:
            raise ValueError("Auction not found")
        
        # Check status
        if auction_data['status'] != "ACTIVE":
            raise ValueError(f"Auction is {auction_data['status']}")
        
        # Check end time
        end_time = datetime.fromisoformat(auction_data['end_time'])
        if datetime.now() > end_time:
            raise ValueError("Auction has ended")
        
        # Check minimum bid (quick check from cache)
        # Note: Worker will do full validation with lock
        min_required = auction_data['current_price'] + auction_data['min_increment']
        if bid_amount < min_required:
            raise ValueError(f"Bid must be at least ${min_required:.2f}")
        
        return auction_data
    
    @staticmethod
    def queue_bid(
        auction_id: int,
        user_id: int,
        bid_amount: float
    ) -> Dict:
        """
        Add bid to processing queue
        
        Args:
            auction_id: Auction ID
            user_id: User ID
            bid_amount: Bid amount
            
        Returns:
            Queue result with bid_id
        """
        redis_client = get_redis_client()
        queue = BidQueue(redis_client)
        
        # Add to queue
        bid_id = queue.enqueue_bid(
            auction_id=auction_id,
            user_id=user_id,
            bid_amount=bid_amount
        )
        
        # Get queue position
        queue_position = queue.get_queue_length(auction_id)
        
        # Estimate processing time
        estimated_seconds = queue_position * 0.1
        if estimated_seconds < 1:
            estimated_time = "< 1 second"
        elif estimated_seconds < 60:
            estimated_time = f"{int(estimated_seconds)} seconds"
        else:
            estimated_time = f"{int(estimated_seconds / 60)} minutes"
        
        return {
            "bid_id": bid_id,
            "status": "QUEUED",
            "queue_position": queue_position,
            "estimated_time": estimated_time
        }
    
    @staticmethod
    def get_bid_status(bid_id: str) -> Optional[Dict]:
        """
        Get bid processing status
        
        Args:
            bid_id: Bid UUID
            
        Returns:
            Status dict or None if not found
        """
        redis_client = get_redis_client()
        queue = BidQueue(redis_client)
        
        return queue.get_bid_status(bid_id)
    
    # @staticmethod
    # def get_bid_history(
    #     auction_id: int,
    #     limit: int = 50,
    #     db: Session = None
    # ) -> List[Dict]:
    #     """
    #     Get bid history for auction
        
    #     Args:
    #         auction_id: Auction ID
    #         limit: Maximum results
    #         db: Database session
            
    #     Returns:
    #         List of bids
    #     """
    #     bids = db.query(Bid).filter(
    #         Bid.auction_id == auction_id
    #     ).order_by(Bid.bid_time.desc()).limit(limit).all()
        
    #     return [bid.to_dict() for bid in bids]
    
    @staticmethod
    def get_bid_history(
        auction_id: int,
        limit: int = 50,
        db: Session = None
    ) -> List[Dict]:
        """
        Get bid history for auction
        
        Args:
            auction_id: Auction ID
            limit: Maximum results
            db: Database session
            
        Returns:
            List of bids
        """
        cache = get_cache_manager()
        return cache.get_recent_bids(auction_id, limit, db)
    
    @staticmethod
    def get_user_bids(
        user_id: int,
        limit: int = 50,
        db: Session = None
    ) -> List[Dict]:
        """
        Get all bids by a user
        
        Args:
            user_id: User ID
            limit: Maximum results
            db: Database session
            
        Returns:
            List of user's bids
        """
        bids = db.query(Bid).filter(
            Bid.user_id == user_id
        ).order_by(Bid.bid_time.desc()).limit(limit).all()
        
        return [bid.to_dict() for bid in bids]
    
    @staticmethod
    def get_winning_bids(
        user_id: int,
        db: Session = None
    ) -> List[Dict]:
        """
        Get auctions where user is currently winning
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            List of auctions where user is winning
        """
        auctions = db.query(Auction).filter(
            Auction.current_winner_id == user_id,
            Auction.status == "ACTIVE"
        ).all()
        
        return [auction.to_dict() for auction in auctions]