"""
Background worker for expiring old HOLD bookings with cache invalidation
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Booking, EventSeat, Event
from app.models.booking import BookingStatus
from app.models.event_seat import SeatStatus
from app.services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)


class ExpiryWorker:
    """Background worker for expiring HOLD bookings"""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the background worker"""
        if self.running:
            logger.warning("⚠️  Expiry worker already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info(f"✅ Expiry worker started (interval: {settings.HOLD_EXPIRY_CHECK_INTERVAL_SECONDS}s)")
    
    async def stop(self):
        """Stop the background worker"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Expiry worker stopped")
    
    async def _run(self):
        """Main worker loop"""
        while self.running:
            try:
                await self._expire_old_holds()
                await asyncio.sleep(settings.HOLD_EXPIRY_CHECK_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in expiry worker: {e}")
                await asyncio.sleep(settings.HOLD_EXPIRY_CHECK_INTERVAL_SECONDS)
    
    async def _expire_old_holds(self):
        """
        Find and expire all HOLD bookings that have passed their expiry time
        
        Cache invalidation:
        - Deletes event:{event_id}:seats for each affected event
        - Deletes event:{event_id}:availability
        """
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    # Find expired holds
                    now = datetime.utcnow()
                    expired_query = select(Booking).where(
                        and_(
                            Booking.status == BookingStatus.HOLD,
                            Booking.hold_expires_at < now
                        )
                    ).with_for_update()
                    
                    result = await db.execute(expired_query)
                    expired_bookings = result.scalars().all()
                    
                    if not expired_bookings:
                        return
                    
                    logger.info(f"⏰ Expiring {len(expired_bookings)} bookings...")
                    
                    # Track affected events for cache invalidation
                    affected_events = set()
                    booking_data = []  # Store data for later broadcast
                    
                    for booking in expired_bookings:
                        # Update booking status
                        booking.status = BookingStatus.EXPIRED
                        
                        # Release seats
                        seats_query = select(EventSeat).where(
                            EventSeat.current_booking_id == booking.id
                        )
                        seats_result = await db.execute(seats_query)
                        seats = seats_result.scalars().all()
                        seat_ids = [seat.id for seat in seats]
                        
                        for seat in seats:
                            seat.status = SeatStatus.AVAILABLE
                            seat.current_booking_id = None
                        
                        # Update event available_seats counter
                        event_query = select(Event).where(Event.id == booking.event_id)
                        event_result = await db.execute(event_query)
                        event = event_result.scalar_one()
                        event.available_seats += len(seats)
                        
                        # Track event for cache invalidation
                        affected_events.add(booking.event_id)
                        booking_data.append({
                            'event_id': booking.event_id,
                            'booking_id': booking.id,
                            'seat_ids': seat_ids
                        })
                        
                        logger.info(f"  ✅ Expired booking {booking.id} - released {len(seats)} seats")

                    await db.commit()
                
                # ✅ Invalidate cache for all affected events
                for event_id in affected_events:
                    logger.info(f"🗑️ Invalidating cache for event {event_id} after expiry")
                    await CacheService.invalidate_event_seats(event_id)
                
                # ✅ FINALLY send WebSocket broadcasts (after cache is cleared)
                for data in booking_data:
                    try:
                        from app.services.websocket_manager import manager
                        logger.info(f"📡 Broadcasting expiry for booking {data['booking_id']}")
                        await manager.broadcast_booking_expiry(
                            event_id=data['event_id'],
                            booking_id=data['booking_id'],
                            seat_ids=data['seat_ids']
                        )
                    except Exception as ws_error:
                        logger.warning(f"  ⚠️  WebSocket broadcast failed: {ws_error}")
             
            except Exception as e:
                logger.error(f"❌ Error expiring holds: {e}")
                await db.rollback()


# Global worker instance
expiry_worker = ExpiryWorker()


async def start_expiry_worker():
    """Start the expiry worker"""
    await expiry_worker.start()


async def stop_expiry_worker():
    """Stop the expiry worker"""
    await expiry_worker.stop()
