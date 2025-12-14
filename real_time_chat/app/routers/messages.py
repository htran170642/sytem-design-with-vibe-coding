"""
Room message endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services import UserService, MessageService, cache_service
from app.schemas.message import MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/")
def get_messages(
    room_id: str = "general",
    limit: int = 50,
    before_id: Optional[int] = None,
    use_cache: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get messages from a room with cursor-based pagination
    
    Args:
        room_id: Room identifier
        limit: Maximum messages to return (max 100)
        before_id: Get messages before this ID (for pagination)
        use_cache: Whether to use Redis cache
    """
    if limit > 100:
        limit = 100
    
    # Try cache first
    if use_cache:
        cache_key = f"messages:{room_id}:{limit}:{before_id or 'latest'}"
        cached = cache_service.get(cache_key)
        
        if cached:
            print(f"[CACHE HIT] {cache_key}")
            return cached
        
        print(f"[CACHE MISS] {cache_key}")
    
    # Get from database
    messages = MessageService.get_messages(
        db,
        room_id=room_id,
        limit=limit,
        before_id=before_id
    )
    
    result = {
        "messages": [
            {
                "id": msg.id,
                "user_id": msg.user_id,
                "username": msg.user.username,
                "room_id": msg.room_id,
                "content": msg.content,
                "created_at": str(msg.created_at)
            }
            for msg in messages
        ],
        "count": len(messages),
        "has_more": len(messages) == limit,
        "next_cursor": messages[-1].id if messages else None
    }
    
    # Cache result
    if use_cache:
        cache_service.set(cache_key, result, ttl=60)
    
    return result


@router.post("/send")
def send_message_http(
    username: str,
    content: str,
    room_id: str = "general",
    db: Session = Depends(get_db)
):
    """Send message via HTTP (for testing/API access)"""
    
    # Get user
    user = UserService.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create message
    message = MessageService.create_message(
        db,
        user_id=user.id,
        content=content,
        room_id=room_id
    )
    
    # Invalidate cache
    cache_service.invalidate_messages_cache(room_id)
    
    return {
        "id": message.id,
        "user_id": user.id,
        "username": username,
        "content": content,
        "room_id": room_id,
        "created_at": str(message.created_at)
    }


@router.get("/rooms")
def get_room_list(db: Session = Depends(get_db)):
    """Get list of all chat rooms"""
    rooms = MessageService.get_room_list(db)
    
    return {
        "rooms": rooms,
        "count": len(rooms)
    }


@router.get("/count/{room_id}")
def get_message_count(room_id: str, db: Session = Depends(get_db)):
    """Get total message count in a room"""
    count = MessageService.get_message_count(db, room_id)
    
    return {
        "room_id": room_id,
        "count": count
    }