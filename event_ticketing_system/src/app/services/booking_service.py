"""
Booking Service with Redis cache invalidation
"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Booking, BookingSeat, EventSeat, Event
from app.models.booking import BookingStatus
from app.models.event_seat import SeatStatus
from app.services.websocket_manager import manager
from app.services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)


class BookingServiceError(Exception):
    """Base exception for booking service errors"""
    pass


class SeatsUnavailableError(BookingServiceError):
    """Raised when requested seats are not available"""
    pass


class BookingNotFoundError(BookingServiceError):
    """Raised when booking doesn't exist"""
    pass


class BookingExpiredError(BookingServiceError):
    """Raised when trying to confirm an expired booking"""
    pass


class EventNotFoundError(BookingServiceError):
    """Raised when event doesn't exist"""
    pass


class TooManyActiveHoldsError(BookingServiceError):
    """Raised when user has too many active holds"""
    pass


class BookingService:
    """Service for managing bookings with cache invalidation"""
    
    @staticmethod
    async def create_hold(
        db: AsyncSession,
        user_id: int,
        event_id: int,
        seat_ids: List[int]
    ) -> Booking:
        """
        Create a booking with HOLD status
        
        Cache invalidation:
        - Deletes event:{event_id}:seats
        - Deletes event:{event_id}:availability
        """
        
        if len(seat_ids) == 0:
            raise BookingServiceError("At least one seat must be selected")
        
        if len(seat_ids) > settings.MAX_SEATS_PER_BOOKING:
            raise BookingServiceError(
                f"Cannot book more than {settings.MAX_SEATS_PER_BOOKING} seats at once"
            )
        
        async with db.begin():
            # 1. Verify event exists and is active
            event_query = select(Event).where(
                Event.id == event_id,
                Event.is_active == True
            )
            event_result = await db.execute(event_query)
            event = event_result.scalar_one_or_none()
            
            if not event:
                raise EventNotFoundError(f"Event {event_id} not found or inactive")
            
            # 2. Check user's active holds
            active_holds_query = select(func.count(Booking.id)).where(
                Booking.user_id == user_id,
                Booking.status == BookingStatus.HOLD
            )
            active_holds_result = await db.execute(active_holds_query)
            active_holds_count = active_holds_result.scalar()
            
            if active_holds_count >= settings.MAX_ACTIVE_HOLDS_PER_USER:
                raise TooManyActiveHoldsError(
                    f"Cannot have more than {settings.MAX_ACTIVE_HOLDS_PER_USER} active holds"
                )
            
            # 3. Lock seats with FOR UPDATE NOWAIT
            seats_query = (
                select(EventSeat)
                .where(EventSeat.id.in_(seat_ids))
                .where(EventSeat.event_id == event_id)
                .where(EventSeat.status == SeatStatus.AVAILABLE)
                .with_for_update(nowait=True)
            )
            
            try:
                seats_result = await db.execute(seats_query)
                seats = seats_result.scalars().all()
            except Exception:
                raise SeatsUnavailableError(
                    "One or more seats are being booked by another user"
                )
            
            # 4. Validate we got all requested seats
            if len(seats) != len(seat_ids):
                unavailable_ids = set(seat_ids) - {seat.id for seat in seats}
                raise SeatsUnavailableError(
                    f"Seats {unavailable_ids} are not available"
                )
            
            # 5. Calculate total amount
            total_amount = sum(seat.price for seat in seats)
            
            # 6. Create booking record
            booking = Booking(
                user_id=user_id,
                event_id=event_id,
                status=BookingStatus.HOLD,
                total_amount=total_amount,
                hold_expires_at=datetime.utcnow() + timedelta(
                    minutes=settings.HOLD_DURATION_MINUTES
                )
            )
            db.add(booking)
            await db.flush()
            
            # 7. Update seat statuses
            for seat in seats:
                seat.status = SeatStatus.HOLD
                seat.current_booking_id = booking.id
            
            # 8. Create booking_seats records
            for seat in seats:
                booking_seat = BookingSeat(
                    booking_id=booking.id,
                    seat_id=seat.id,
                    price_at_booking=seat.price
                )
                db.add(booking_seat)
            
            # 9. Update event available_seats counter
            event.available_seats -= len(seats)
            
            await db.commit()
        
        # 10. ✅ Invalidate cache
        logger.info(f"🗑️ Invalidating cache for event {event_id} after HOLD booking")
        await CacheService.invalidate_event_seats(event_id)
        
        # 11. Broadcast WebSocket update
        await manager.broadcast_seat_update(
            event_id=event_id,
            seat_ids=seat_ids,
            new_status="HOLD",
            booking_id=booking.id
        )
        
        # 12. Load relationships and return
        query = (
            select(Booking)
            .where(Booking.id == booking.id)
            .options(
                selectinload(Booking.booking_seats).selectinload(BookingSeat.seat)
            )
        )
        result = await db.execute(query)
        return result.scalar_one()
    
    @staticmethod
    async def confirm_booking(
        db: AsyncSession,
        booking_id: int,
        user_id: int,
        payment_id: Optional[str] = None
    ) -> Booking:
        """
        Confirm a HOLD booking
        
        Cache invalidation:
        - Deletes event:{event_id}:seats
        - Deletes event:{event_id}:availability
        """
        async with db.begin():
            booking_query = (
                select(Booking)
                .where(Booking.id == booking_id)
                .where(Booking.user_id == user_id)
                .with_for_update()
            )
            booking_result = await db.execute(booking_query)
            booking = booking_result.scalar_one_or_none()
            
            if not booking:
                raise BookingNotFoundError(f"Booking {booking_id} not found")
            
            if booking.status != BookingStatus.HOLD:
                raise BookingServiceError(
                    f"Booking is in {booking.status.value} status, cannot confirm"
                )
            
            if booking.hold_expires_at and datetime.utcnow() > booking.hold_expires_at:
                raise BookingExpiredError("Booking hold has expired")
            
            booking.status = BookingStatus.CONFIRMED
            booking.confirmed_at = datetime.utcnow()
            booking.payment_id = payment_id
            booking.hold_expires_at = None
            
            # Get seat IDs for broadcast
            seats_query = select(EventSeat.id).where(
                EventSeat.current_booking_id == booking_id
            )
            seats_result = await db.execute(seats_query)
            seat_ids = [row[0] for row in seats_result.all()]
            
            # Update seats to BOOKED
            seats_query = select(EventSeat).where(
                EventSeat.current_booking_id == booking_id
            )
            seats_result = await db.execute(seats_query)
            seats = seats_result.scalars().all()
            
            for seat in seats:
                seat.status = SeatStatus.BOOKED
            
            await db.commit()
        
        # ✅ Invalidate cache
        logger.info(f"🗑️ Invalidating cache for event {booking.event_id} after CONFIRM")
        await CacheService.invalidate_event_seats(booking.event_id)
        
        # Broadcast WebSocket update
        await manager.broadcast_seat_update(
            event_id=booking.event_id,
            seat_ids=seat_ids,
            new_status="BOOKED",
            booking_id=booking_id
        )
        
        # Load and return
        query = (
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.booking_seats).selectinload(BookingSeat.seat)
            )
        )
        result = await db.execute(query)
        return result.scalar_one()
    
    @staticmethod
    async def cancel_booking(
        db: AsyncSession,
        booking_id: int,
        user_id: int
    ) -> Booking:
        """
        Cancel a booking
        
        Cache invalidation:
        - Deletes event:{event_id}:seats
        - Deletes event:{event_id}:availability
        """
        async with db.begin():
            booking_query = (
                select(Booking)
                .where(Booking.id == booking_id)
                .where(Booking.user_id == user_id)
                .with_for_update()
            )
            booking_result = await db.execute(booking_query)
            booking = booking_result.scalar_one_or_none()
            
            if not booking:
                raise BookingNotFoundError(f"Booking {booking_id} not found")
            
            if booking.status == BookingStatus.CANCELLED:
                raise BookingServiceError("Booking already cancelled")
            
            old_status = booking.status
            booking.status = BookingStatus.CANCELLED
            booking.cancelled_at = datetime.utcnow()
            
            # Get seats
            seats_query = select(EventSeat).where(
                EventSeat.current_booking_id == booking_id
            )
            seats_result = await db.execute(seats_query)
            seats = seats_result.scalars().all()
            seat_ids = [seat.id for seat in seats]
            
            for seat in seats:
                seat.status = SeatStatus.AVAILABLE
                seat.current_booking_id = None
            
            if old_status in [BookingStatus.HOLD, BookingStatus.CONFIRMED]:
                event_query = select(Event).where(Event.id == booking.event_id)
                event_result = await db.execute(event_query)
                event = event_result.scalar_one()
                event.available_seats += len(seats)
            
            await db.commit()
        
        # ✅ Invalidate cache
        logger.info(f"🗑️ Invalidating cache for event {booking.event_id} after CANCEL")
        await CacheService.invalidate_event_seats(booking.event_id)
        
        # Broadcast WebSocket update
        await manager.broadcast_seat_update(
            event_id=booking.event_id,
            seat_ids=seat_ids,
            new_status="AVAILABLE",
            booking_id=booking_id
        )
        
        # Load and return
        query = (
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.booking_seats).selectinload(BookingSeat.seat)
            )
        )
        result = await db.execute(query)
        return result.scalar_one()
    
    @staticmethod
    async def get_user_bookings(
        db: AsyncSession,
        user_id: int,
        status: Optional[BookingStatus] = None
    ) -> List[Booking]:
        """Get all bookings for a user with relationships loaded"""
        query = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .options(
                selectinload(Booking.booking_seats).selectinload(BookingSeat.seat)
            )
            .order_by(Booking.created_at.desc())
        )
        
        if status:
            query = query.where(Booking.status == status)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_booking_by_id(
        db: AsyncSession,
        booking_id: int,
        user_id: int
    ) -> Optional[Booking]:
        """Get a specific booking with relationships loaded"""
        query = (
            select(Booking)
            .where(Booking.id == booking_id, Booking.user_id == user_id)
            .options(
                selectinload(Booking.booking_seats).selectinload(BookingSeat.seat)
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
