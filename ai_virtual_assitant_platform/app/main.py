"""
AIVA - AI Virtual Assistant Platform
Main application entry point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import health, ai, documents, auth
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import get_logger
from app.core.middleware import (
    PrometheusMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    APIKeyAuthMiddleware,
    RateLimitMiddleware,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Runs on startup and shutdown
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API Host: {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"Rate limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Virtual Assistant Platform with RAG capabilities",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
# IMPORTANT: Order matters! Middleware runs in REVERSE order
# So add them in this order:
# BEST PRACTICE ORDER:
app.add_middleware(PrometheusMiddleware)       # 5️⃣ Runs 5th - outermost, captures full latency
app.add_middleware(APIKeyAuthMiddleware)       # 4️⃣ Runs 4th - after rate check
app.add_middleware(RateLimitMiddleware)        # 3️⃣ Runs 3rd - BEFORE auth
app.add_middleware(RequestLoggingMiddleware)   # 2️⃣ Runs 2nd
app.add_middleware(RequestIDMiddleware)        # 1️⃣ Runs 1st

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(ai.router)
app.include_router(documents.router)
app.include_router(auth.router)

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "running",
        "docs_url": "/docs" if settings.ENABLE_DOCS else None,
        "features": {
            "rag": settings.ENABLE_RAG,
            "background_jobs": settings.ENABLE_BACKGROUND_JOBS,
            "caching": settings.ENABLE_CACHING,
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )