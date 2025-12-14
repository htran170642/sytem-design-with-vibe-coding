"""
Auction API Routes - WITH CACHE
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.infrastructure.database import get_db
from app.infrastructure.cache import get_cache_manager  # ← ADD THIS
from app.services import AuctionService

router = APIRouter(prefix="/auctions", tags=["auctions"])


class CreateAuctionRequest(BaseModel):
    title: str
    description: str
    starting_price: float
    min_increment: float
    duration_minutes: int


@router.post("")
async def create_auction(request: CreateAuctionRequest, db: Session = Depends(get_db)):
    """Create a new auction"""
    try:
        auction = AuctionService.create_auction(
            title=request.title,
            description=request.description,
            starting_price=request.starting_price,
            min_increment=request.min_increment,
            duration_minutes=request.duration_minutes,
            db=db
        )
        
        return {
            "success": True,
            "message": "Auction created successfully",
            "auction": auction.to_dict()
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_auctions(
    status: str = None,
    include_bids: bool = False,  # ← Changed to False (faster)
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all auctions - USES CACHE via service layer
    """
    auctions = AuctionService.list_auctions(
        status=status,
        include_bids=include_bids,
        limit=limit,  # ← Add limit
        db=db
    )
    
    return {
        "total": len(auctions),
        "auctions": auctions
    }


@router.get("/{auction_id}")
async def get_auction(auction_id: int, db: Session = Depends(get_db)):
    """
    Get specific auction - USES CACHE!
    
    This is the critical endpoint for performance tests.
    """
    # ════════════════════════════════════════════════════════════
    # FIX: Use cache instead of database!
    # ════════════════════════════════════════════════════════════
    cache = get_cache_manager()
    
    # Get from cache (fast!)
    auction_data = cache.get_auction(auction_id, db)
    
    if not auction_data:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Get recent bids (can use cache too!)
    from app.services import BidService
    bids = BidService.get_bid_history(auction_id, limit=10, db=db)
    
    # Add queue length (real-time data, not cached)
    from app.infrastructure.queue import BidQueue
    from app.infrastructure.redis_client import get_redis_client
    redis_client = get_redis_client()
    queue = BidQueue(redis_client)
    auction_data["queued_bids"] = queue.get_queue_length(auction_id)
    
    return {
        "auction": auction_data,  # ← Now from cache!
        "recent_bids": bids,
        "bid_count": auction_data["total_bids"]
    }


@router.get("/{auction_id}/statistics")
async def get_auction_statistics(auction_id: int, db: Session = Depends(get_db)):
    """Get auction statistics"""
    try:
        stats = AuctionService.get_auction_statistics(auction_id, db)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))