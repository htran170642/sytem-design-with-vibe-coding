"""
Direct message model
"""
from sqlalchemy import Column, Integer, Text, DateTime, Index, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class DirectMessage(Base):
    """Direct message model - stores one-to-one messages"""
    __tablename__ = "direct_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_read = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_direct_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_direct_messages")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_conversation', 'sender_id', 'receiver_id', 'created_at'),
        Index('idx_receiver_unread', 'receiver_id', 'is_read', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DirectMessage(id={self.id}, from={self.sender_id}, to={self.receiver_id})>"