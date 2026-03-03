"""
Core package
Contains configuration, logging, middleware, exceptions, and security
"""

# Configuration
from app.core.config import settings, Settings

# Logging
from app.core.logging_config import get_logger, setup_logging

# Exception handling
from app.core.exceptions import (
    AIVAException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ExternalServiceError,
    LLMError,
    VectorDBError,
    DocumentProcessingError,
    ConfigurationError,
)
from app.core.exception_handlers import register_exception_handlers

# Middleware
from app.core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    APIKeyAuthMiddleware,
    RateLimitMiddleware,
)

# Security
from app.core.security import (
    verify_api_key,
    optional_api_key,
    get_current_user,
)

__all__ = [
    # Configuration
    "settings",
    "Settings",
    # Logging
    "get_logger",
    "setup_logging",
    # Exceptions
    "AIVAException",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
    "LLMError",
    "VectorDBError",
    "DocumentProcessingError",
    "ConfigurationError",
    # Exception handlers
    "register_exception_handlers",
    # Middleware
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "APIKeyAuthMiddleware",
    "RateLimitMiddleware",
    # Security
    "verify_api_key",
    "optional_api_key",
    "get_current_user",
]