"""Pydantic schemas for Booking resources"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, computed_field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    event_id: int = Field(..., gt=0)
    seat_ids: List[int] = Field(..., min_length=1, max_length=10)


class BookingConfirm(BaseModel):
    payment_id: Optional[str] = Field(None, max_length=255)


class BookingSeatResponse(BaseModel):
    seat_id: int
    section: str
    row_number: str
    seat_number: str
    price_at_booking: Decimal
    seat_label: str
    
    @classmethod
    def from_booking_seat(cls, booking_seat):
        """Convert BookingSeat ORM model to response"""
        return cls(
            seat_id=booking_seat.seat_id,
            section=booking_seat.seat.section,
            row_number=booking_seat.seat.row_number,
            seat_number=booking_seat.seat.seat_number,
            price_at_booking=booking_seat.price_at_booking,
            seat_label=booking_seat.seat.seat_label,
        )


class BookingResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    status: BookingStatus
    total_amount: Decimal
    hold_expires_at: Optional[datetime] = None
    payment_id: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    seats: List[BookingSeatResponse] = Field(default_factory=list)
    time_remaining_seconds: int = 0
    
    @classmethod
    def from_booking(cls, booking):
        """Convert Booking ORM model to response"""
        # Calculate time remaining
        time_remaining = 0
        if booking.status == BookingStatus.HOLD and booking.hold_expires_at:
            remaining = (booking.hold_expires_at - datetime.utcnow()).total_seconds()
            time_remaining = max(0, int(remaining))
        
        return cls(
            id=booking.id,
            user_id=booking.user_id,
            event_id=booking.event_id,
            status=booking.status,
            total_amount=booking.total_amount,
            hold_expires_at=booking.hold_expires_at,
            payment_id=booking.payment_id,
            created_at=booking.created_at,
            confirmed_at=booking.confirmed_at,
            cancelled_at=booking.cancelled_at,
            seats=[BookingSeatResponse.from_booking_seat(bs) for bs in booking.booking_seats],
            time_remaining_seconds=time_remaining,
        )
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    bookings: List[BookingResponse]
    total: int
