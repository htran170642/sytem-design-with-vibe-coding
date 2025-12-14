"""
Pydantic schemas for Seat resources
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

from app.models.event_seat import SeatStatus


class SeatBase(BaseModel):
    """Base Seat schema"""
    section: str = Field(..., max_length=50, description="Seat section")
    row_number: str = Field(..., max_length=10, description="Row number")
    seat_number: str = Field(..., max_length=10, description="Seat number")
    price: Decimal = Field(..., description="Seat price")


class SeatResponse(SeatBase):
    """Seat response schema"""
    id: int
    event_id: int
    status: SeatStatus = Field(..., description="Seat status (AVAILABLE, HOLD, BOOKED)")
    seat_label: str = Field(..., description="Human-readable seat label")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SeatMapResponse(BaseModel):
    """Response schema for seat map"""
    event_id: int
    seats: list[SeatResponse]
    total_seats: int
    available_seats: int
    
    # Grouping by section for easier frontend rendering
    sections: dict[str, list[SeatResponse]] = Field(
        default_factory=dict,
        description="Seats grouped by section"
    )
