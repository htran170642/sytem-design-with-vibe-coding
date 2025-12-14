"""
Direct message service - business logic for one-to-one messages
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
from typing import List, Optional, Dict
from datetime import datetime

from app.models import DirectMessage, User


class DirectMessageService:
    """Service for direct message operations"""
    
    @staticmethod
    def send_message(
        db: Session,
        sender_id: int,
        receiver_id: int,
        content: str
    ) -> DirectMessage:
        """
        Send a direct message
        
        Args:
            db: Database session
            sender_id: Sender user ID
            receiver_id: Receiver user ID
            content: Message content
            
        Returns:
            Created direct message
        """
        dm = DirectMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content
        )
        db.add(dm)
        db.commit()
        db.refresh(dm)
        
        return dm
    
    @staticmethod
    def get_conversation(
        db: Session,
        user1_id: int,
        user2_id: int,
        limit: int = 50,
        before_id: Optional[int] = None
    ) -> List[DirectMessage]:
        """
        Get conversation between two users
        
        Args:
            db: Database session
            user1_id: First user ID
            user2_id: Second user ID
            limit: Maximum messages
            before_id: Cursor for pagination
            
        Returns:
            List of messages
        """
        query = db.query(DirectMessage).filter(
            or_(
                and_(
                    DirectMessage.sender_id == user1_id,
                    DirectMessage.receiver_id == user2_id
                ),
                and_(
                    DirectMessage.sender_id == user2_id,
                    DirectMessage.receiver_id == user1_id
                )
            )
        )
        
        if before_id:
            query = query.filter(DirectMessage.id < before_id)
        
        messages = query.order_by(desc(DirectMessage.created_at)).limit(limit).all()
        
        return list(reversed(messages))
    
    @staticmethod
    def get_conversations_list(db: Session, user_id: int) -> List[Dict]:
        """
        Get list of all conversations for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of conversation summaries
        """
        # Get all messages where user is sender or receiver
        all_messages = db.query(DirectMessage).filter(
            or_(
                DirectMessage.sender_id == user_id,
                DirectMessage.receiver_id == user_id
            )
        ).order_by(desc(DirectMessage.created_at)).all()
        
        # Group by conversation partner
        conversations_dict = {}
        
        for msg in all_messages:
            # Determine the other user
            if msg.sender_id == user_id:
                other_user_id = msg.receiver_id
                other_user = msg.receiver
            else:
                other_user_id = msg.sender_id
                other_user = msg.sender
            
            # Only keep most recent message per conversation
            if other_user_id not in conversations_dict:
                # Count unread messages
                unread_count = db.query(DirectMessage).filter(
                    DirectMessage.sender_id == other_user_id,
                    DirectMessage.receiver_id == user_id,
                    DirectMessage.is_read == False
                ).count()
                
                conversations_dict[other_user_id] = {
                    "other_user": {
                        "id": other_user.id,
                        "username": other_user.username
                    },
                    "last_message": {
                        "content": msg.content,
                        "created_at": msg.created_at,
                        "is_mine": msg.sender_id == user_id
                    },
                    "unread_count": unread_count
                }
        
        # Convert to list and sort by most recent
        conversation_list = list(conversations_dict.values())
        conversation_list.sort(
            key=lambda x: x['last_message']['created_at'],
            reverse=True
        )
        
        return conversation_list
    
    @staticmethod
    def get_unread_messages(db: Session, user_id: int) -> List[DirectMessage]:
        """
        Get all unread messages for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of unread messages
        """
        return db.query(DirectMessage).filter(
            DirectMessage.receiver_id == user_id,
            DirectMessage.is_read == False
        ).order_by(desc(DirectMessage.created_at)).all()
    
    @staticmethod
    def mark_as_read(db: Session, message_id: int, user_id: int) -> bool:
        """
        Mark a message as read
        
        Args:
            db: Database session
            message_id: Message ID
            user_id: User ID (must be receiver)
            
        Returns:
            True if successful
        """
        message = db.query(DirectMessage).filter(
            DirectMessage.id == message_id
        ).first()
        
        if not message or message.receiver_id != user_id:
            return False
        
        message.is_read = True
        db.commit()
        
        return True
    
    @staticmethod
    def mark_conversation_as_read(db: Session, user_id: int, other_user_id: int) -> int:
        """
        Mark all messages in a conversation as read
        
        Args:
            db: Database session
            user_id: Current user ID (receiver)
            other_user_id: Other user ID (sender)
            
        Returns:
            Number of messages marked as read
        """
        result = db.query(DirectMessage).filter(
            DirectMessage.sender_id == other_user_id,
            DirectMessage.receiver_id == user_id,
            DirectMessage.is_read == False
        ).update({"is_read": True})
        
        db.commit()
        
        return result
    
    @staticmethod
    def delete_message(db: Session, message_id: int) -> bool:
        """
        Delete a direct message
        
        Args:
            db: Database session
            message_id: Message ID
            
        Returns:
            True if successful
        """
        message = db.query(DirectMessage).filter(
            DirectMessage.id == message_id
        ).first()
        
        if not message:
            return False
        
        db.delete(message)
        db.commit()
        
        return True