"""
Room message model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class Message(Base):
    """Message model - stores room/group chat messages"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    room_id = Column(String(50), default="general", nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship to user
    user = relationship("User", back_populates="messages")
    
    # Composite index for common query pattern
    __table_args__ = (
        Index('idx_room_created', 'room_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, user_id={self.user_id}, content='{self.content[:20]}...')>"