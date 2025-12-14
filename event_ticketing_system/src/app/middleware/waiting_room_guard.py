"""
Waiting Room Guard Middleware
Ensures users can only book if admitted through waiting room
"""
from fastapi import Request, HTTPException
from typing import Optional
import logging

from app.services.waiting_room import waiting_room_service

logger = logging.getLogger(__name__)


async def check_waiting_room_access(
    request: Request,
    event_id: int,
    token: Optional[str] = None
) -> bool:
    """
    Check if user has valid waiting room access
    
    Args:
        request: FastAPI request
        event_id: Event ID being accessed
        token: Waiting room token (from header or query param)
    
    Returns:
        True if access granted
        
    Raises:
        HTTPException if waiting room is enabled and user not admitted
    """
    # Check if waiting room is enabled for this event
    is_enabled = await waiting_room_service.is_enabled(event_id)
    
    if not is_enabled:
        # Waiting room disabled, allow access
        logger.debug(f"Waiting room disabled for event {event_id}, allowing access")
        return True
    
    # Waiting room is enabled - check token
    if not token:
        logger.warning(f"No waiting room token provided for event {event_id}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "waiting_room_required",
                "message": "This event requires waiting room access",
                "event_id": event_id,
                "action": "join_queue",
                "endpoint": f"/api/v1/events/{event_id}/waiting-room/join"
            }
        )
    
    # Verify token is in active set
    is_active = await waiting_room_service.redis.redis.sismember(
        f"waiting_room:{event_id}:active",
        token
    )
    
    if not is_active:
        logger.warning(f"Invalid or expired waiting room token for event {event_id}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "waiting_room_token_invalid",
                "message": "Your waiting room session has expired or is invalid",
                "event_id": event_id,
                "action": "rejoin_queue",
                "endpoint": f"/api/v1/events/{event_id}/waiting-room/join"
            }
        )
    
    logger.info(f"✅ Valid waiting room access for event {event_id}")
    return True