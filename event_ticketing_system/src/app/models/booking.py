"""
Booking model - Manages seat reservations with hold/confirm flow
"""
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.core.database import Base


class BookingStatus(PyEnum):
    """Enum for booking status"""
    HOLD = "HOLD"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.HOLD, index=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    hold_expires_at = Column(DateTime, nullable=True, index=True)  # NULL when CONFIRMED
    payment_id = Column(String(255), nullable=True)  # Stripe payment intent ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="bookings")
    event = relationship("Event", back_populates="bookings")
    held_seats = relationship("EventSeat", foreign_keys="EventSeat.current_booking_id", 
                             back_populates="current_booking")
    booking_seats = relationship("BookingSeat", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<Booking(id={self.id}, user_id={self.user_id}, event_id={self.event_id}, "
                f"status='{self.status.value}', total=${self.total_amount})>")
    
    @property
    def is_expired(self) -> bool:
        """Check if hold has expired"""
        if self.status != BookingStatus.HOLD or self.hold_expires_at is None:
            return False
        return datetime.utcnow() > self.hold_expires_at
    
    @property
    def is_confirmed(self) -> bool:
        """Check if booking is confirmed"""
        return self.status == BookingStatus.CONFIRMED
    
    @property
    def can_confirm(self) -> bool:
        """Check if booking can be confirmed"""
        return self.status == BookingStatus.HOLD and not self.is_expired
    
    @property
    def time_remaining_seconds(self) -> int:
        """Get remaining hold time in seconds"""
        if self.status != BookingStatus.HOLD or self.hold_expires_at is None:
            return 0
        remaining = (self.hold_expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    @classmethod
    def create_hold_expiry(cls, hold_duration_minutes: int = 5) -> datetime:
        """Create expiry timestamp for new hold"""
        return datetime.utcnow() + timedelta(minutes=hold_duration_minutes)
