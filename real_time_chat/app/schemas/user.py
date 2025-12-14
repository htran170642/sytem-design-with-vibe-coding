"""
User Pydantic schemas
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user schema"""
    username: str
    email: str


class UserCreate(UserBase):
    """Schema for creating user"""
    pass


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    created_at: datetime
    last_seen: datetime
    is_online: bool
    
    class Config:
        from_attributes = True


class UserListItem(BaseModel):
    """Schema for user in list"""
    id: int
    username: str
    is_online: bool
    last_seen: datetime
    
    class Config:
        from_attributes = True