"""
Bid API Routes

Handles:
- Placing bids (async)
- Checking bid status
- Getting bid history
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.infrastructure.database import get_db
from app.infrastructure.queue import BidQueue
from app.infrastructure.cache import get_cache
from app.infrastructure.redis_client import get_redis_client
from app.models import Auction, Bid
from datetime import datetime
from app.services import BidService

# Create router
router = APIRouter(
    prefix="/bids",
    tags=["bids"]
)


# ============================================================================
# REQUEST MODELS
# ============================================================================
class PlaceBidRequest(BaseModel):
    """Request model for placing bid"""
    user_id: int
    bid_amount: float


# ============================================================================
# ROUTES
# ============================================================================
@router.post("/auctions/{auction_id}/bids/async")
async def place_bid_async(
    auction_id: int,
    request: PlaceBidRequest,
    db: Session = Depends(get_db)
):
    """Place bid asynchronously"""
    try:
        # Validate using service
        BidService.validate_bid(
            auction_id=auction_id,
            user_id=request.user_id,
            bid_amount=request.bid_amount,
            db=db
        )
        
        # Queue using service
        result = BidService.queue_bid(
            auction_id=auction_id,
            user_id=request.user_id,
            bid_amount=request.bid_amount
        )
        
        return {
            "success": True,
            "message": "Your bid is being processed",
            **result,
            "check_status_url": f"/bids/{result['bid_id']}/status"
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/{bid_id}/status")
async def get_bid_status(bid_id: str):
    """Check bid status"""
    status = BidService.get_bid_status(bid_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Bid not found or expired")
    
    return status


@router.get("/auctions/{auction_id}/bids")
async def get_auction_bids(
    auction_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get bid history for auction
    
    Args:
        auction_id: Auction ID
        limit: Maximum number of bids to return
        db: Database session
        
    Returns:
        List of bids for this auction
    """
    # Use AuctionService to get auction (includes validation)
    from app.services import AuctionService
    
    auction = AuctionService.get_auction(auction_id, db)
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Use BidService to get bid history
    bids = BidService.get_bid_history(
        auction_id=auction_id,
        limit=limit,
        db=db
    )
    
    return {
        "auction_id": auction_id,
        "total_bids": auction.total_bids,
        "bids": bids  # Already converted to dict in service
    }
    
@router.get("/users/{user_id}/bids")
async def get_user_bids(
    user_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get all bids by a specific user
    
    Args:
        user_id: User ID
        limit: Maximum number of bids to return
        db: Database session
        
    Returns:
        List of user's bids across all auctions
    """
    bids = BidService.get_user_bids(
        user_id=user_id,
        limit=limit,
        db=db
    )
    
    return {
        "user_id": user_id,
        "total_bids": len(bids),
        "bids": bids
    }


@router.get("/users/{user_id}/winning")
async def get_user_winning_bids(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get auctions where user is currently winning
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        List of auctions where user is winning
    """
    winning_auctions = BidService.get_winning_bids(
        user_id=user_id,
        db=db
    )
    
    return {
        "user_id": user_id,
        "winning_count": len(winning_auctions),
        "auctions": winning_auctions
    }