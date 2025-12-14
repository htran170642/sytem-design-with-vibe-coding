"""
User model
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class User(Base):
    """User model - stores user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_online = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    messages = relationship("Message", back_populates="user")
    sent_direct_messages = relationship(
        "DirectMessage",
        foreign_keys="DirectMessage.sender_id",
        back_populates="sender"
    )
    received_direct_messages = relationship(
        "DirectMessage",
        foreign_keys="DirectMessage.receiver_id",
        back_populates="receiver"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', online={self.is_online})>"