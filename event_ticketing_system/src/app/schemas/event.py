"""
Pydantic schemas for Event resources
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EventBase(BaseModel):
    """Base Event schema"""
    name: str = Field(..., max_length=500, description="Event name")
    description: Optional[str] = Field(None, description="Event description")
    venue: str = Field(..., max_length=500, description="Venue name")
    city: str = Field(..., max_length=100, description="City")
    country: str = Field(..., max_length=100, description="Country")
    start_time: datetime = Field(..., description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    category: Optional[str] = Field(None, max_length=100, description="Event category")
    image_url: Optional[str] = Field(None, max_length=500, description="Event image URL")


class EventResponse(EventBase):
    """Event response schema"""
    id: int
    total_seats: int = Field(..., description="Total number of seats")
    available_seats: int = Field(..., description="Available seats for booking")
    is_active: bool = Field(..., description="Whether event is active")
    is_sold_out: bool = Field(..., description="Whether event is sold out")
    occupancy_rate: float = Field(..., description="Occupancy percentage")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Response schema for listing events"""
    events: list[EventResponse]
    total: int
    page: int
    page_size: int
