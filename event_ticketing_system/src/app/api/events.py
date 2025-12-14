"""
Events API endpoints - Read-only operations
Uses EventService for business logic
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.event_seat import SeatStatus
from app.schemas import EventResponse, EventListResponse, SeatMapResponse, SeatResponse
from app.services import EventService, EventNotFoundError

from app.middleware.rate_limiter import limiter
from app.middleware.anti_bot import anti_bot
from app.middleware.waiting_room_guard import check_waiting_room_access

router = APIRouter()


@router.get("/events", response_model=EventListResponse)
@limiter.limit("30/minute")
async def list_events(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    city: Optional[str] = Query(None, description="Filter by city"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: bool = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all events with pagination and filtering
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 10, max: 100)
    - **city**: Filter by city (optional)
    - **category**: Filter by category (optional)
    - **is_active**: Filter by active status (default: True)
    """
    try:
        events, total = await EventService.list_events(
            db=db,
            page=page,
            page_size=page_size,
            city=city,
            category=category,
            is_active=is_active,
        )
        
        return EventListResponse(
            events=[EventResponse.model_validate(event) for event in events],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/events/search", response_model=EventListResponse)
@limiter.limit("20/minute")
async def search_events(
    request: Request,
    q: str = Query(..., description="Search term", min_length=1),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search events by name, venue, city, or description
    
    - **q**: Search term (required)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 10, max: 100)
    """
    try:
        events, total = await EventService.search_events(
            db=db,
            search_term=q,
            page=page,
            page_size=page_size,
        )
        
        return EventListResponse(
            events=[EventResponse.model_validate(event) for event in events],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/events/{event_id}", response_model=EventResponse)
@limiter.limit("60/minute")
async def get_event(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific event by ID
    
    - **event_id**: Event ID
    """
    try:
        event = await EventService.get_event_by_id(db=db, event_id=event_id)
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        return EventResponse.model_validate(event)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/events/{event_id}/seats", response_model=SeatMapResponse)
@limiter.limit("20/minute")
async def get_event_seats(
    request: Request,
    event_id: int,
    section: Optional[str] = Query(None, description="Filter by section"),
    status: Optional[SeatStatus] = Query(None, description="Filter by status"),
    user_id: Optional[int] = Query(None, description="User ID for anti-bot tracking"),
    wr_token: Optional[str] = Query(None, description="Waiting room token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get seat map for an event
    
    - **event_id**: Event ID
    - **section**: Filter by section (optional)
    - **status**: Filter by status (AVAILABLE, HOLD, BOOKED) (optional)
    """
    # Check waiting room access
    await check_waiting_room_access(request, event_id, wr_token)
    
    # Anti-bot protection
    ip = request.client.host
    await anti_bot.check_seat_probing(ip=ip, user_id=user_id)
    
    try:
        seats, sections_dict = await EventService.get_event_seats(
            db=db,
            event_id=event_id,
            section=section,
            status=status,
        )
        
        # Convert to response models
        seat_responses = [SeatResponse.model_validate(seat) for seat in seats]
        
        # Convert sections_dict to response format
        sections_response = {
            section_name: [SeatResponse.model_validate(seat) for seat in section_seats]
            for section_name, section_seats in sections_dict.items()
        }
        
        # Count available seats
        available_count = sum(1 for seat in seats if seat.status == SeatStatus.AVAILABLE)
        
        return SeatMapResponse(
            event_id=event_id,
            seats=seat_responses,
            total_seats=len(seats),
            available_seats=available_count,
            sections=sections_response,
        )
    except EventNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/events/{event_id}/availability")
@limiter.limit("30/minute")
async def get_event_availability(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed availability breakdown by section
    
    Returns statistics for each section:
    - Total seats
    - Available seats
    - Seats on hold
    - Booked seats
    
    - **event_id**: Event ID
    """
    try:
        # Verify event exists
        event = await EventService.get_event_by_id(db=db, event_id=event_id)
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        # Get section availability
        section_stats = await EventService.get_section_availability(db=db, event_id=event_id)
        
        return {
            "event_id": event_id,
            "event_name": event.name,
            "sections": section_stats,
            "total_seats": event.total_seats,
            "available_seats": event.available_seats,
        }
    except HTTPException:
        raise
    except EventNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
