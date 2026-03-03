"""
Authentication Dependencies
FastAPI dependencies for authentication and authorization
"""

from typing import Optional

from fastapi import Header, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core import settings, get_logger

logger = get_logger(__name__)

# Security scheme for API key
security = HTTPBearer(auto_error=False)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Verify API key from header
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Validate API key
    if x_api_key != settings.API_KEY:
        logger.warning(
            "Invalid API key attempted",
            extra={"provided_key": x_api_key[:8] + "..."},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    logger.debug("API key validated successfully")
    return x_api_key


async def optional_api_key(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    """
    Optional API key verification
    Returns None if no key provided, validates if provided
    
    Args:
        x_api_key: Optional API key from X-API-Key header
        
    Returns:
        The API key if provided and valid, None otherwise
        
    Raises:
        HTTPException: If API key is provided but invalid
    """
    if not x_api_key:
        return None
    
    # If provided, must be valid
    if x_api_key != settings.API_KEY:
        logger.warning(
            "Invalid API key attempted",
            extra={"provided_key": x_api_key[:8] + "..."},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return x_api_key


async def get_current_user(api_key: str = Depends(verify_api_key)) -> dict:
    """
    Get current user based on API key
    Placeholder for future user management
    
    Args:
        api_key: Validated API key
        
    Returns:
        User information dictionary
    """
    # TODO: Replace with actual user lookup in Phase 7
    return {
        "user_id": "default_user",
        "api_key": api_key,
        "permissions": ["read", "write"],
    }