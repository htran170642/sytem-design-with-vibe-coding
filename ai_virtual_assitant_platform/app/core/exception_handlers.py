"""
Exception Handlers
Global exception handlers for FastAPI application
"""

import traceback
from typing import Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AIVAException
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def aiva_exception_handler(request: Request, exc: AIVAException) -> JSONResponse:
    """
    Handler for custom AIVA exceptions
    
    Args:
        request: FastAPI request
        exc: AIVA exception instance
        
    Returns:
        JSON response with error details
    """
    logger.error(
        f"AIVA Exception: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details,
        },
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.details if exc.details else None,
        },
    )


async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handler for Pydantic validation errors
    
    Args:
        request: FastAPI request
        exc: Validation error instance
        
    Returns:
        JSON response with validation error details
    """
    errors = []
    
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    logger.warning(
        "Validation error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        },
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "detail": {"errors": errors},
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handler for HTTP exceptions
    
    Args:
        request: FastAPI request
        exc: HTTP exception instance
        
    Returns:
        JSON response with error details
    """
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unexpected exceptions
    
    Args:
        request: FastAPI request
        exc: Exception instance
        
    Returns:
        JSON response with error details
    """
    # Log full traceback for debugging
    logger.error(
        f"Unexpected error: {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
    )
    
    # In development, include traceback
    response_content = {
        "success": False,
        "error": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred",
    }
    
    if settings.DEBUG:
        response_content["detail"] = {
            "exception": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc().split("\n"),
        }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content,
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    # Custom AIVA exceptions
    app.add_exception_handler(AIVAException, aiva_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Catch-all for unexpected exceptions
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered")