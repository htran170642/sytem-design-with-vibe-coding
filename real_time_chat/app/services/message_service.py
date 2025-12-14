"""
Message service - business logic for room messages
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime

from app.models import Message, User


class MessageService:
    """Service for room message operations"""
    
    @staticmethod
    def create_message(
        db: Session,
        user_id: int,
        content: str,
        room_id: str = "general"
    ) -> Message:
        """
        Create a new message
        
        Args:
            db: Database session
            user_id: Sender user ID
            content: Message content
            room_id: Room identifier
            
        Returns:
            Created message
        """
        message = Message(
            user_id=user_id,
            room_id=room_id,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return message
    
    @staticmethod
    def get_messages(
        db: Session,
        room_id: str = "general",
        limit: int = 50,
        before_id: Optional[int] = None
    ) -> List[Message]:
        """
        Get messages from a room with cursor-based pagination
        
        Args:
            db: Database session
            room_id: Room identifier
            limit: Maximum messages to return
            before_id: Cursor - get messages before this ID
            
        Returns:
            List of messages
        """
        query = db.query(Message).filter(Message.room_id == room_id)
        
        if before_id:
            query = query.filter(Message.id < before_id)
        
        messages = query.order_by(desc(Message.created_at)).limit(limit).all()
        
        return list(reversed(messages))
    
    @staticmethod
    def get_message_by_id(db: Session, message_id: int) -> Optional[Message]:
        """Get message by ID"""
        return db.query(Message).filter(Message.id == message_id).first()
    
    @staticmethod
    def delete_message(db: Session, message_id: int) -> bool:
        """
        Delete a message
        
        Args:
            db: Database session
            message_id: Message ID
            
        Returns:
            True if successful
        """
        message = MessageService.get_message_by_id(db, message_id)
        if not message:
            return False
        
        db.delete(message)
        db.commit()
        
        return True
    
    @staticmethod
    def get_room_list(db: Session) -> List[str]:
        """
        Get list of all room IDs
        
        Returns:
            List of room IDs
        """
        result = db.query(Message.room_id).distinct().all()
        return [room[0] for room in result]
    
    @staticmethod
    def get_message_count(db: Session, room_id: str = "general") -> int:
        """
        Get total message count in a room
        
        Args:
            db: Database session
            room_id: Room identifier
            
        Returns:
            Message count
        """
        return db.query(Message).filter(Message.room_id == room_id).count()