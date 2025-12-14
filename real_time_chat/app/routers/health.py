"""
Health check and statistics endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, check_database_health, get_pool_status, get_query_stats
from app.services import cache_service
from app.utils.websocket_manager import ws_manager
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Health check endpoint"""
    from datetime import datetime
    
    db_healthy = check_database_health()
    
    try:
        redis_stats = cache_service.get_stats()
        redis_healthy = "error" not in redis_stats
    except:
        redis_healthy = False
    
    return {
        "status": "healthy" if (db_healthy and redis_healthy) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "up" if db_healthy else "down",
            "redis": "up" if redis_healthy else "down"
        },
        "pool": get_pool_status(),
        "websocket": {
            "active_connections": ws_manager.get_online_count()
        }
    }


@router.get("/stats/pool")
def get_pool_stats():
    """Get connection pool statistics"""
    return get_pool_status()


@router.get("/stats/queries")
def get_query_statistics():
    """Get query execution statistics"""
    stats = get_query_stats()
    
    total = stats['total_queries']
    slow = stats['slow_queries']
    
    return {
        **stats,
        "slow_query_percentage": round((slow / total * 100) if total > 0 else 0, 2)
    }


@router.get("/stats/redis")
def get_redis_stats():
    """Get Redis statistics"""
    return cache_service.get_stats()


@router.get("/stats/websocket")
def get_websocket_stats():
    """Get WebSocket statistics"""
    return {
        "active_connections": ws_manager.get_online_count()
    }