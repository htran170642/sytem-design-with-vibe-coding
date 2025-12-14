"""
BookingSeat model - Junction table linking bookings to seats
Preserves historical pricing information
"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class BookingSeat(Base):
    __tablename__ = "booking_seats"
    __table_args__ = (
        UniqueConstraint('booking_id', 'seat_id', name='uq_booking_seat'),
    )

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(Integer, ForeignKey("event_seats.id", ondelete="CASCADE"), nullable=False, index=True)
    price_at_booking = Column(Numeric(10, 2), nullable=False)  # Snapshot of price at booking time
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    booking = relationship("Booking", back_populates="booking_seats")
    seat = relationship("EventSeat", back_populates="booking_seats")

    def __repr__(self):
        return f"<BookingSeat(id={self.id}, booking_id={self.booking_id}, seat_id={self.seat_id}, price=${self.price_at_booking})>"
