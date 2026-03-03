"""
Health Check Router
Provides endpoints for monitoring application health
"""

import time
from typing import Dict, Any

from fastapi import APIRouter, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Store application start time
START_TIME = time.time()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    app_name: str
    version: str
    environment: str
    uptime_seconds: float


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status"""
    status: str
    app_name: str
    version: str
    environment: str
    uptime_seconds: float
    components: Dict[str, Any]
    timestamp: float


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns basic application health status"
)
async def health_check():
    """
    Basic health check endpoint
    
    Returns:
        HealthResponse: Basic health information
    """
    uptime = time.time() - START_TIME
    
    logger.debug("Health check requested")
    
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime_seconds=round(uptime, 2),
    )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Returns detailed health status including all components"
)
async def detailed_health_check():
    """
    Detailed health check endpoint
    
    Checks status of:
    - Application
    - Configuration
    - Feature flags
    
    Returns:
        DetailedHealthResponse: Detailed health information
    """
    uptime = time.time() - START_TIME
    
    # Check components
    components = {
        "application": {
            "status": "healthy",
            "uptime_seconds": round(uptime, 2),
        },
        "configuration": {
            "status": "healthy",
            "debug_mode": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
        },
        "features": {
            "status": "healthy",
            "docs_enabled": settings.ENABLE_DOCS,
            "rag_enabled": settings.ENABLE_RAG,
            "background_jobs_enabled": settings.ENABLE_BACKGROUND_JOBS,
            "caching_enabled": settings.ENABLE_CACHING,
        },
    }
    
    # Determine overall status
    overall_status = "healthy"
    for component_name, component_info in components.items():
        if component_info.get("status") != "healthy":
            overall_status = "degraded"
            break
    
    logger.debug("Detailed health check requested")
    
    return DetailedHealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime_seconds=round(uptime, 2),
        components=components,
        timestamp=time.time(),
    )


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Checks if application is ready to accept traffic (Kubernetes readiness probe)"
)
async def readiness_check():
    """
    Readiness check for Kubernetes/load balancers
    
    Returns 200 if the application is ready to serve traffic
    Returns 503 if the application is not ready
    """
    # For now, always ready if application is running
    # In future, check database, redis, etc.
    
    is_ready = True
    
    if is_ready:
        return {
            "status": "ready",
            "message": "Application is ready to serve traffic"
        }
    else:
        return {
            "status": "not_ready",
            "message": "Application is not ready"
        }


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Checks if application is alive (Kubernetes liveness probe)"
)
async def liveness_check():
    """
    Liveness check for Kubernetes

    Returns 200 if the application is alive
    Should be restarted if this returns non-200
    """
    return {
        "status": "alive",
        "message": "Application is alive"
    }


@router.get(
    "/metrics",
    include_in_schema=False,
    summary="Prometheus metrics",
    description="Prometheus text-format metrics for scraping",
)
async def prometheus_metrics():
    """
    Prometheus metrics scrape endpoint.

    Returns all registered metrics in Prometheus text format.
    Suitable for use as a Prometheus scrape target.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get(
    "/health/cache-stats",
    status_code=status.HTTP_200_OK,
    summary="Cache statistics",
    description="Returns cache hit/miss statistics since last process start"
)
async def cache_stats():
    """
    Cache hit/miss statistics endpoint

    Returns current hit/miss counters and hit rate from the shared
    CacheService instance. Counters reset on process restart.
    """
    from app.services.cache_service import get_cache_service

    cache = get_cache_service()
    stats = cache.get_stats()

    return {
        "cache_enabled": settings.CACHE_ENABLED,
        "hits": stats.hits,
        "misses": stats.misses,
        "hit_rate": f"{stats.hit_rate:.1%}",
    }