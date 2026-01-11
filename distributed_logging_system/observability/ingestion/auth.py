"""Authentication for the ingestion service.

This module provides API key-based authentication for securing
the ingestion endpoints.
"""
from typing import Optional

from fastapi import Header, HTTPException, status

from observability.common.config import get_settings
from observability.common.logger import get_logger

logger = get_logger(__name__)


class AuthenticationError(HTTPException):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "ApiKey"},
        )


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify API key from request header.
    
    This is a FastAPI dependency that validates the API key
    from the X-API-Key header.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        AuthenticationError: If API key is missing or invalid
        
    Example:
        ```python
        @app.post("/logs")
        async def ingest_logs(
            batch: LogBatch,
            api_key: str = Depends(verify_api_key)  # Validates API key
        ):
            # This only runs if API key is valid
            pass
        ```
    """
    settings = get_settings()
    
    # Check if API key was provided
    if not x_api_key:
        logger.warning("Request missing API key")
        raise AuthenticationError("API key required")
    
    # Validate against configured API key
    # In production, you'd check against a database of valid keys
    if x_api_key != settings.ingestion_api_key:
        logger.warning(
            "Invalid API key attempted",
            key_prefix=x_api_key[:8] if len(x_api_key) >= 8 else "***"
        )
        raise AuthenticationError("Invalid API key")
    
    logger.debug("API key validated successfully")
    return x_api_key


class APIKeyValidator:
    """API key validator for more complex scenarios.
    
    This class can be extended to support:
    - Multiple API keys
    - Key rotation
    - Key-specific rate limits
    - Key expiration
    - Database-backed key storage
    """

    def __init__(self):
        """Initialize the validator."""
        self.settings = get_settings()
        # In production, load valid keys from database
        self.valid_keys = {
            self.settings.ingestion_api_key: {
                "name": "default-key",
                "rate_limit": 1000,  # requests per minute
                "created_at": "2024-01-01",
            }
        }

    def validate(self, api_key: str) -> dict:
        """Validate an API key and return its metadata.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            Dictionary with key metadata
            
        Raises:
            AuthenticationError: If key is invalid
        """
        if api_key not in self.valid_keys:
            raise AuthenticationError("Invalid API key")
        
        return self.valid_keys[api_key]

    def is_valid(self, api_key: str) -> bool:
        """Check if an API key is valid.
        
        Args:
            api_key: The API key to check
            
        Returns:
            True if valid, False otherwise
        """
        return api_key in self.valid_keys

    def add_key(self, api_key: str, metadata: dict) -> None:
        """Add a new valid API key.
        
        Args:
            api_key: The API key to add
            metadata: Metadata about the key
        """
        self.valid_keys[api_key] = metadata
        logger.info("New API key added", key_name=metadata.get("name"))

    def revoke_key(self, api_key: str) -> None:
        """Revoke an API key.
        
        Args:
            api_key: The API key to revoke
        """
        if api_key in self.valid_keys:
            key_name = self.valid_keys[api_key].get("name")
            del self.valid_keys[api_key]
            logger.info("API key revoked", key_name=key_name)


# Global validator instance
# In production, this would be initialized from database
validator = APIKeyValidator()