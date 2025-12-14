"""
FastAPI Dependencies
"""
from sqlalchemy.orm import Session
from app.infrastructure.database import SessionLocal
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.cache import get_cache
from app.infrastructure.queue import BidQueue
from app.infrastructure.pubsub import get_pubsub_manager


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis():
    """Get Redis client"""
    return get_redis_client()


def get_auction_cache():
    """Get auction cache"""
    redis = get_redis_client()
    return get_cache(redis)


def get_bid_queue():
    """Get bid queue"""
    redis = get_redis_client()
    return BidQueue(redis)


def get_pubsub():
    """Get Pub/Sub manager"""
    return get_pubsub_manager()