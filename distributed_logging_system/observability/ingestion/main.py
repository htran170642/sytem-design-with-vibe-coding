"""Main FastAPI application for the ingestion service.

This module creates and configures the FastAPI app that receives
logs and metrics from collection agents.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from observability.common.config import get_settings
from observability.common.logger import get_logger
from observability.ingestion.auth import AuthenticationError
from observability.ingestion.kafka_producer import close_producer
from observability.ingestion.rate_limiter import RateLimitExceeded
from observability.ingestion.routes import router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager.
    
    This handles startup and shutdown events for the FastAPI app.
    
    Startup:
    - Log application start
    - Initialize connections (Kafka, etc.)
    
    Shutdown:
    - Close Kafka producer
    - Cleanup resources
    """
    # Startup
    settings = get_settings()
    logger.info(
        "Ingestion service starting",
        environment=settings.environment,
        log_level=settings.log_level,
    )
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Ingestion service shutting down")
    await close_producer()
    logger.info("Ingestion service stopped")


# Create FastAPI application
app = FastAPI(
    title="Observability Ingestion Service",
    description="Receives logs and metrics from collection agents and writes to Kafka",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Add CORS middleware (for web clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routes
app.include_router(router, prefix="", tags=["ingestion"])


# Exception handlers

@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    """Handle authentication errors.
    
    Returns 401 Unauthorized with error details.
    """
    logger.warning(
        "Authentication failed",
        path=request.url.path,
        error=exc.detail,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_error_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Handle rate limit errors.
    
    Returns 429 Too Many Requests with retry information.
    """
    logger.warning(
        "Rate limit exceeded",
        path=request.url.path,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation errors.
    
    Returns 422 Unprocessable Entity with validation details.
    """
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        errors=exc.errors(),
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected errors.
    
    Returns 500 Internal Server Error.
    """
    logger.error(
        "Unexpected error",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": str(exc),
        },
    )


# Request logging middleware

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests.
    
    Logs:
    - Request method and path
    - Response status code
    - Request duration
    """
    import time
    
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log request
    logger.info(
        "HTTP request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
    )
    
    return response


# Main entry point for running with uvicorn

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "observability.ingestion.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )