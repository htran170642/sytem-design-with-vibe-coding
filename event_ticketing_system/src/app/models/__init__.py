"""
SQLAlchemy Models for Event Ticket Booking System

Import all models here for easy access and to ensure proper relationship setup.
"""
from app.core.database import Base

# Import all models to register them with SQLAlchemy
from app.models.user import User
from app.models.event import Event
from app.models.event_seat import EventSeat, SeatStatus
from app.models.booking import Booking, BookingStatus
from app.models.booking_seat import BookingSeat

# Export all models
__all__ = [
    "Base",
    "User",
    "Event",
    "EventSeat",
    "SeatStatus",
    "Booking",
    "BookingStatus",
    "BookingSeat",
]
