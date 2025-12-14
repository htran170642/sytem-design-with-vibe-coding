"""
Rate limiting middleware using SlowAPI
Protects against abuse and DDoS attacks
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import logging

logger = logging.getLogger(__name__)


def get_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting
    Combines IP address and user_id if available
    """
    # Get IP address
    ip = get_remote_address(request)
    
    # Try to get user_id from query params
    user_id = request.query_params.get('user_id')
    
    if user_id:
        # Rate limit by user_id (more strict)
        return f"user:{user_id}"
    
    # Fallback to IP address
    return f"ip:{ip}"


# Create limiter instance
limiter = Limiter(
    key_func=get_identifier,
    default_limits=["100/minute"],  # Global default
    storage_uri="redis://localhost:6379/1",  # Use Redis DB 1 for rate limiting
    strategy="fixed-window"  # Can also use "moving-window"
)
