"""
Main FastAPI Application
Phase 5: Complete Auction System with Queue, Cache, and Pub/Sub
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database import get_db, init_db, SessionLocal
from app.infrastructure.redis_client import test_redis_connection, get_redis_client
from app.infrastructure.cache import get_cache_manager

from app.infrastructure.queue import BidQueue
from app.infrastructure.pubsub import get_pubsub_manager
from app.models import Auction, Bid

# Import routers
from app.api import auctions, bids, admin, websockets

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================
app.include_router(auctions.router)
app.include_router(bids.router)
app.include_router(admin.router)
app.include_router(websockets.router)


# ============================================================================
# STARTUP / SHUTDOWN EVENTS
# ============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize on server start"""
    print("\n" + "=" * 70)
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 70)
    
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized")
    
    print("🔌 Testing Redis connection...")
    if test_redis_connection():
        print("✅ Redis connected")
    else:
        print("⚠️  WARNING: Redis not connected!")
    
    print("📡 Initializing Pub/Sub...")
    pubsub = get_pubsub_manager()
    await pubsub.connect()
    print("✅ Pub/Sub ready")
    
    print("🔥 Warming cache...")
    cache = get_cache_manager()
  
    db = SessionLocal()
    try:
        cache.warm(db)
    finally:
        db.close()
    
    print("✅ Startup complete")
    print("=" * 70 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server stop"""
    print("\n👋 Shutting down...")
    pubsub = get_pubsub_manager()
    await pubsub.disconnect()
    print("✅ Shutdown complete\n")


# ============================================================================
# ROOT ENDPOINT
# ============================================================================
@app.get("/", tags=["root"])
async def root(db: Session = Depends(get_db)):
    """Server status and statistics"""
    total_auctions = db.query(Auction).count()
    total_bids = db.query(Bid).count()
    active_auctions = db.query(Auction).filter(Auction.status == "ACTIVE").count()
    
    redis_status = "✅ Connected" if test_redis_connection() else "❌ Disconnected"
    
    redis_client = get_redis_client()
    queue = BidQueue(redis_client)
    
    active_auction_list = db.query(Auction).filter(Auction.status == "ACTIVE").all()
    total_queued = sum(
        queue.get_queue_length(auction.auction_id) 
        for auction in active_auction_list
    )
    
    return {
        "message": f"{settings.APP_NAME} v{settings.APP_VERSION}",
        "status": "running",
        "total_auctions": total_auctions,
        "active_auctions": active_auctions,
        "total_bids": total_bids,
        "queued_bids": total_queued,
        "database": "PostgreSQL ✅",
        "redis": redis_status,
        "features": [
            "Message Queue System",
            "Redis Pub/Sub",
            "Caching Layer",
            "Distributed Locks",
            "WebSocket Real-Time Updates"
        ]
    }