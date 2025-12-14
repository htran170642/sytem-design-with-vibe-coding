"""
Event Service with Redis caching
"""
from typing import List, Tuple, Optional, Dict
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventSeat
from app.models.event_seat import SeatStatus
from app.schemas.seat import SeatResponse
from app.services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)


class EventNotFoundError(Exception):
    """Raised when event is not found"""
    pass


class EventService:
    """Service for event-related operations with caching"""
    
    @staticmethod
    async def list_events(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        city: Optional[str] = None,
        category: Optional[str] = None,
        is_active: bool = True,
    ) -> Tuple[List[Event], int]:
        """List events with pagination and filters"""
        query = select(Event).where(Event.is_active == is_active)
        
        if city:
            query = query.where(Event.city == city)
        if category:
            query = query.where(Event.category == category)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Get paginated results
        query = query.order_by(Event.start_time.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        events = result.scalars().all()
        
        return events, total
    
    @staticmethod
    async def get_event_by_id(db: AsyncSession, event_id: int) -> Event:
        """Get event by ID with caching"""
        query = select(Event).where(Event.id == event_id)
        result = await db.execute(query)
        event = result.scalar_one_or_none()
        
        if not event:
            raise EventNotFoundError(f"Event {event_id} not found")
        
        # Cache the result
        event_dict = {
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "venue": event.venue,
            "city": event.city,
            "country": event.country,
            "start_time": event.start_time.isoformat(),
            "total_seats": event.total_seats,
            "available_seats": event.available_seats,
            "category": event.category,
        }
        await CacheService.set_event(event_id, event_dict)
        
        return event
    
    @staticmethod
    async def get_event_seats(
        db: AsyncSession,
        event_id: int,
        section: Optional[str] = None,
        status: Optional[SeatStatus] = None,
    ) -> Tuple[List[SeatResponse], Dict[str, List[SeatResponse]]]:
        """
        Get seat map with caching
        
        Cache key: event:{event_id}:seats
        TTL: 1 minute (volatile data)
        """
        # Try cache first (only if no filters)
        if not section and not status:
            cached = await CacheService.get_event_seats(event_id)
            
            if cached:
                logger.info(f"📦 Cache HIT: Returning cached seats for event {event_id}")
                
                # ✅ Convert cached dicts back to SeatResponse objects
                seat_responses = [SeatResponse(**seat) for seat in cached['seats']]
                sections_dict = {
                    k: [SeatResponse(**s) for s in v] 
                    for k, v in cached['sections'].items()
                }
                
                return seat_responses, sections_dict
        
        # Cache MISS or filters applied - fetch from database
        logger.info(f"❌ Cache MISS: Fetching seats for event {event_id} from database")
        
        # Verify event exists
        event_query = select(Event).where(Event.id == event_id)
        event_result = await db.execute(event_query)
        if not event_result.scalar_one_or_none():
            raise EventNotFoundError(f"Event {event_id} not found")
        
        # Build query
        query = select(EventSeat).where(EventSeat.event_id == event_id)
        
        if section:
            query = query.where(EventSeat.section == section)
        if status:
            query = query.where(EventSeat.status == status)
        
        query = query.order_by(EventSeat.section, EventSeat.row_number, EventSeat.seat_number)
        
        result = await db.execute(query)
        seats = result.scalars().all()
        
        # Convert to response objects
        seat_responses = [SeatResponse.model_validate(seat) for seat in seats]
        
        # Group by section
        sections = {}
        for seat in seat_responses:
            if seat.section not in sections:
                sections[seat.section] = []
            sections[seat.section].append(seat)
        
        # Cache if no filters (full seat map)
        if not section and not status:
            # ✅ Use model_dump() which properly serializes enums
            cache_data = {
                'seats': [s.model_dump(mode='json') for s in seat_responses],  # mode='json' for proper enum serialization
                'sections': {k: [s.model_dump(mode='json') for s in v] for k, v in sections.items()}
            }
            
            # Debug: Check what we're caching
            logger.info(f"🔍 Sample cached seat status: {cache_data['seats'][0]['status']}")
            
            await CacheService.set_event_seats(event_id, cache_data)
            logger.info(f"💾 Cached {len(seat_responses)} seats for event {event_id}")
        
        return seat_responses, sections
    
    @staticmethod
    async def get_section_availability(
        db: AsyncSession,
        event_id: int
    ) -> Dict[str, Dict[str, int]]:
        """Get availability summary by section with caching"""
        # Try cache first
        cached = await CacheService.get_event_availability(event_id)
        if cached:
            logger.info(f"📦 Cache HIT: Returning cached availability for event {event_id}")
            return cached
        
        logger.info(f"❌ Cache MISS: Fetching availability for event {event_id} from database")
        
        # Verify event exists
        event_query = select(Event).where(Event.id == event_id)
        event_result = await db.execute(event_query)
        if not event_result.scalar_one_or_none():
            raise EventNotFoundError(f"Event {event_id} not found")
        
        # Get counts by section and status
        query = select(
            EventSeat.section,
            EventSeat.status,
            func.count(EventSeat.id).label('count')
        ).where(
            EventSeat.event_id == event_id
        ).group_by(
            EventSeat.section,
            EventSeat.status
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        # Build availability dict
        availability = {}
        for row in rows:
            section = row.section
            if section not in availability:
                availability[section] = {
                    'total': 0,
                    'available': 0,
                    'hold': 0,
                    'booked': 0
                }
            
            availability[section]['total'] += row.count
            
            if row.status == SeatStatus.AVAILABLE:
                availability[section]['available'] = row.count
            elif row.status == SeatStatus.HOLD:
                availability[section]['hold'] = row.count
            elif row.status == SeatStatus.BOOKED:
                availability[section]['booked'] = row.count
        
        # Cache the result
        await CacheService.set_event_availability(event_id, availability)
        logger.info(f"💾 Cached availability for event {event_id}")
        
        return availability
    
    @staticmethod
    async def search_events(
        db: AsyncSession,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Event], int]:
        """Search events by name, venue, city, or description"""
        search_pattern = f"%{query}%"
        
        search_query = select(Event).where(
            or_(
                Event.name.ilike(search_pattern),
                Event.venue.ilike(search_pattern),
                Event.city.ilike(search_pattern),
                Event.description.ilike(search_pattern),
            ),
            Event.is_active == True
        )
        
        # Get total count
        count_query = select(func.count()).select_from(search_query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Get paginated results
        search_query = search_query.order_by(Event.start_time.asc())
        search_query = search_query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(search_query)
        events = result.scalars().all()
        
        return events, total
