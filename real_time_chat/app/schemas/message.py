"""
Message Pydantic schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MessageCreate(BaseModel):
    """Schema for creating message"""
    content: str
    room_id: str = "general"


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: int
    user_id: int
    username: str
    room_id: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DirectMessageCreate(BaseModel):
    """Schema for creating direct message"""
    receiver_username: str
    content: str


class DirectMessageResponse(BaseModel):
    """Schema for direct message response"""
    id: int
    sender_id: int
    sender: str
    receiver_id: int
    receiver: str
    content: str
    created_at: datetime
    is_read: bool
    
    class Config:
        from_attributes = True