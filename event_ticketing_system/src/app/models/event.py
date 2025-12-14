"""
Event model for managing ticketed events
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    venue = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    country = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    total_seats = Column(Integer, nullable=False, default=0)
    available_seats = Column(Integer, nullable=False, default=0)
    category = Column(String(100), index=True)  # 'concert', 'sports', 'theater'
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    seats = relationship("EventSeat", back_populates="event", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="event")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name}', venue='{self.venue}', start='{self.start_time}')>"
    
    @property
    def is_sold_out(self) -> bool:
        """Check if event is sold out"""
        return self.available_seats <= 0
    
    @property
    def occupancy_rate(self) -> float:
        """Calculate current occupancy percentage"""
        if self.total_seats == 0:
            return 0.0
        return ((self.total_seats - self.available_seats) / self.total_seats) * 100
