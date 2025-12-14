"""
FastAPI application entry point with surge handling
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
import logging

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_client
from app.api import events, bookings, websocket, cache, waiting_room
from app.services import start_expiry_worker, stop_expiry_worker
from app.middleware.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting up Event Ticketing System...")
    logger.info(f"📊 Database: {settings.DATABASE_URL.split('@')[1]}")
    
    # Test database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    # Connect to Redis
    logger.info("🔴 Connecting to Redis...")
    await redis_client.connect()
    
    # Start background workers
    logger.info("⏰ Starting expiry worker...")
    await start_expiry_worker()
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    await stop_expiry_worker()
    await redis_client.close()
    await engine.dispose()
    logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A high-performance event ticket booking system with surge handling",
    lifespan=lifespan,
)

# Add rate limiter state
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors"""
    logger.warning(f"⚠️ Rate limit exceeded for {request.url.path}")
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": str(exc.detail)
        },
        headers={
            "Retry-After": "60"  # Tell client to retry after 60 seconds
        }
    )


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    redis_status = "healthy" if redis_client.redis else "unavailable"
    
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "redis": redis_status,
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Event Ticketing System API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/events/{event_id}",
        "features": [
            "Real-time seat updates via WebSocket",
            "Redis caching for performance",
            "Automatic booking expiry",
            "Rate limiting and anti-bot protection",
            "Virtual waiting room for surge traffic",
            "Idempotency for safe retries"
        ]
    }


# Include routers
app.include_router(events.router, prefix="/api/v1", tags=["Events"])
app.include_router(bookings.router, prefix="/api/v1", tags=["Bookings"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(cache.router, prefix="/api/v1", tags=["Cache"])
app.include_router(waiting_room.router, prefix="/api/v1", tags=["Waiting Room"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
