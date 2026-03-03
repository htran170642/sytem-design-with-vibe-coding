"""
Custom Exceptions
Define application-specific exceptions
"""

from typing import Any, Dict, Optional


class AIVAException(Exception):
    """Base exception for all AIVA errors"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AIVAException):
    """Raised when validation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class AuthenticationError(AIVAException):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
        )


class AuthorizationError(AIVAException):
    """Raised when authorization fails"""

    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
        )


class NotFoundError(AIVAException):
    """Raised when a resource is not found"""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource, "resource_id": resource_id},
        )


class ConflictError(AIVAException):
    """Raised when there's a conflict (e.g., duplicate resource)"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class RateLimitError(AIVAException):
    """Raised when rate limit is exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
        )


class ExternalServiceError(AIVAException):
    """Raised when an external service fails"""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{service} error: {message}",
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={**(details or {}), "service": service},
        )


class LLMError(ExternalServiceError):
    """Raised when LLM API fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(service="LLM", message=message, details=details)


class VectorDBError(ExternalServiceError):
    """Raised when vector database fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(service="VectorDB", message=message, details=details)


class DocumentProcessingError(AIVAException):
    """Raised when document processing fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="DOCUMENT_PROCESSING_ERROR",
            details=details,
        )


class ConfigurationError(AIVAException):
    """Raised when there's a configuration error"""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=500,
            error_code="CONFIGURATION_ERROR",
        )