"""
Admin API Routes - Monitoring and Management
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.infrastructure.cache import get_cache_manager
from app.infrastructure.queue import BidQueue
from app.infrastructure.pubsub import get_pubsub_manager
from app.infrastructure.redis_client import get_redis_client, test_redis_connection
from app.models import Auction

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cache-stats")
async def get_cache_stats():
    """Get cache statistics"""
    cache = get_cache_manager()
    return cache.get_stats()


@router.get("/queue-stats")
async def get_queue_stats(db: Session = Depends(get_db)):
    """Get message queue statistics"""
    redis_client = get_redis_client()
    queue = BidQueue(redis_client)
    
    active_auctions = db.query(Auction).filter(
        Auction.status == "ACTIVE"
    ).all()
    
    total_queued = 0
    queues_with_pending = 0
    queue_details = []
    
    for auction in active_auctions:
        queue_length = queue.get_queue_length(auction.auction_id)
        
        if queue_length > 0:
            queues_with_pending += 1
            queue_details.append({
                "auction_id": auction.auction_id,
                "title": auction.title,
                "queued_bids": queue_length,
                "total_bids": auction.total_bids
            })
        
        total_queued += queue_length
    
    return {
        "total_queued": total_queued,
        "active_auctions": len(active_auctions),
        "queues_with_pending": queues_with_pending,
        "details": queue_details
    }


@router.get("/pubsub-stats")
async def get_pubsub_stats():
    """Get Pub/Sub statistics"""
    pubsub = get_pubsub_manager()
    return pubsub.get_stats()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """System health check"""
    # Check database
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check Redis
    redis_status = "healthy" if test_redis_connection() else "unhealthy"
    
    # Check cache
    cache = get_cache_manager()
    cache_health = cache.health_check()
    
    # Check Pub/Sub
    pubsub = get_pubsub_manager()
    pubsub_stats = pubsub.get_stats()
    pubsub_status = "healthy" if pubsub_stats["is_connected"] else "unhealthy"
    
    # Overall status
    overall = "healthy" if (
        db_status == "healthy" and 
        redis_status == "healthy" and 
        cache_health["status"] == "healthy" and
        pubsub_status == "healthy"
    ) else "degraded"
    
    return {
        "status": overall,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "cache": cache_health["status"],
            "pubsub": pubsub_status
        },
        "details": {
            "cache_stats": cache_health.get("stats", {}),
            "pubsub_stats": pubsub_stats
        }
    }


@router.post("/cache/warm")
async def warm_cache(status: str = "ACTIVE", db: Session = Depends(get_db)):
    """Manually warm cache"""
    cache = get_cache_manager()
    count = cache.warm(db, status=status)
    
    return {
        "success": True,
        "message": f"Warmed cache with {count} {status} auctions",
        "count": count
    }


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all auction caches"""
    cache = get_cache_manager()
    cache.clear_all()
    
    return {
        "success": True,
        "message": "All caches cleared"
    }


@router.post("/cache/invalidate/{auction_id}")
async def invalidate_auction_cache(auction_id: int):
    """Invalidate specific auction cache"""
    cache = get_cache_manager()
    cache.invalidate_auction(auction_id)
    
    return {
        "success": True,
        "message": f"Cache invalidated for auction {auction_id}",
        "auction_id": auction_id
    }