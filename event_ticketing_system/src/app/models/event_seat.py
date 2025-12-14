"""
EventSeat model - CRITICAL for concurrency control
This is the table where race conditions are prevented via row-level locking
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class SeatStatus(PyEnum):
    """Enum for seat status"""
    AVAILABLE = "AVAILABLE"
    HOLD = "HOLD"
    BOOKED = "BOOKED"


class EventSeat(Base):
    __tablename__ = "event_seats"
    __table_args__ = (
        UniqueConstraint('event_id', 'section', 'row_number', 'seat_number', 
                        name='uq_event_seat_location'),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(50), nullable=False)  # 'VIP', 'A', 'B', 'General'
    row_number = Column(String(10), nullable=False)  # 'A', '1', '15'
    seat_number = Column(String(10), nullable=False)  # '1', '12', '101'
    price = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(SeatStatus), nullable=False, default=SeatStatus.AVAILABLE, index=True)
    current_booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=0)  # For optimistic locking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="seats")
    current_booking = relationship("Booking", foreign_keys=[current_booking_id], back_populates="held_seats")
    booking_seats = relationship("BookingSeat", back_populates="seat", cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<EventSeat(id={self.id}, event_id={self.event_id}, "
                f"section='{self.section}', row='{self.row_number}', "
                f"seat='{self.seat_number}', status='{self.status.value}')>")
    
    @property
    def is_available(self) -> bool:
        """Check if seat is available for booking"""
        return self.status == SeatStatus.AVAILABLE
    
    @property
    def seat_label(self) -> str:
        """Human-readable seat label"""
        return f"{self.section}-{self.row_number}-{self.seat_number}"
