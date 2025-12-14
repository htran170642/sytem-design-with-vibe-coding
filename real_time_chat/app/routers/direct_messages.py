"""
Direct message endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services import UserService, DirectMessageService, cache_service
from app.schemas.message import DirectMessageCreate, DirectMessageResponse

router = APIRouter(prefix="/dm", tags=["direct_messages"])


@router.post("/send")
def send_direct_message(
    sender_username: str,
    receiver_username: str,
    content: str,
    db: Session = Depends(get_db)
):
    """Send a direct message to another user"""
    
    # Get sender
    sender = UserService.get_by_username(db, sender_username)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    # Get receiver
    receiver = UserService.get_by_username(db, receiver_username)
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Can't send message to yourself
    if sender.id == receiver.id:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")
    
    # Send message
    dm = DirectMessageService.send_message(
        db,
        sender_id=sender.id,
        receiver_id=receiver.id,
        content=content
    )
    
    # Invalidate cache
    cache_service.invalidate_dm_cache(sender.id, receiver.id)
    
    return {
        "id": dm.id,
        "sender": sender_username,
        "receiver": receiver_username,
        "content": content,
        "created_at": str(dm.created_at),
        "is_read": dm.is_read
    }


@router.get("/conversation/{other_username}")
def get_conversation(
    current_username: str,
    other_username: str,
    limit: int = 50,
    before_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get conversation history between two users"""
    
    # Get current user
    current_user = UserService.get_by_username(db, current_username)
    if not current_user:
        raise HTTPException(status_code=404, detail="Current user not found")
    
    # Get other user
    other_user = UserService.get_by_username(db, other_username)
    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found")
    
    # Get conversation
    messages = DirectMessageService.get_conversation(
        db,
        user1_id=current_user.id,
        user2_id=other_user.id,
        limit=limit,
        before_id=before_id
    )
    
    # Mark messages as read
    DirectMessageService.mark_conversation_as_read(
        db,
        user_id=current_user.id,
        other_user_id=other_user.id
    )
    
    return {
        "messages": [
            {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender": msg.sender.username,
                "receiver_id": msg.receiver_id,
                "receiver": msg.receiver.username,
                "content": msg.content,
                "created_at": str(msg.created_at),
                "is_read": msg.is_read,
                "is_mine": msg.sender_id == current_user.id
            }
            for msg in messages
        ],
        "count": len(messages),
        "has_more": len(messages) == limit,
        "next_cursor": messages[-1].id if messages else None
    }


@router.get("/conversations")
def get_all_conversations(
    username: str,
    db: Session = Depends(get_db)
):
    """Get list of all conversations for a user"""
    
    # Get user
    user = UserService.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get conversations
    conversations = DirectMessageService.get_conversations_list(db, user.id)
    
    return {
        "conversations": [
            {
                "other_user": conv["other_user"],
                "last_message": {
                    "content": conv["last_message"]["content"],
                    "created_at": str(conv["last_message"]["created_at"]),
                    "is_mine": conv["last_message"]["is_mine"]
                },
                "unread_count": conv["unread_count"]
            }
            for conv in conversations
        ],
        "count": len(conversations)
    }


@router.get("/unread")
def get_unread_messages(
    username: str,
    db: Session = Depends(get_db)
):
    """Get all unread messages for a user"""
    
    # Get user
    user = UserService.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get unread messages
    unread = DirectMessageService.get_unread_messages(db, user.id)
    
    return {
        "unread_messages": [
            {
                "id": msg.id,
                "sender": msg.sender.username,
                "content": msg.content,
                "created_at": str(msg.created_at)
            }
            for msg in unread
        ],
        "count": len(unread)
    }


@router.post("/mark-read/{message_id}")
def mark_message_as_read(
    message_id: int,
    username: str,
    db: Session = Depends(get_db)
):
    """Mark a specific message as read"""
    
    # Get user
    user = UserService.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mark as read
    success = DirectMessageService.mark_as_read(db, message_id, user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Message not found or not authorized")
    
    return {"message": "Marked as read"}


@router.post("/mark-read-conversation")
def mark_conversation_read(
    current_username: str,
    other_username: str,
    db: Session = Depends(get_db)
):
    """Mark all unread messages in a conversation as read"""
    current_user = UserService.get_by_username(db, current_username)
    if not current_user:
        raise HTTPException(status_code=404, detail="Current user not found")
    
    other_user = UserService.get_by_username(db, other_username)
    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found")
    
    count = DirectMessageService.mark_conversation_as_read(
        db, user_id=current_user.id, other_user_id=other_user.id
    )
    
    return {"message": "Conversation marked as read", "count": count}