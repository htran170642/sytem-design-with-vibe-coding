"""Bookings API endpoints"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.booking import BookingStatus
from app.schemas import (
    BookingCreate,
    BookingConfirm,
    BookingResponse,
    BookingListResponse,
)
from app.services import (
    BookingService,
    BookingServiceError,
    SeatsUnavailableError,
    BookingNotFoundError,
    BookingExpiredError,
    EventNotFoundError,
    TooManyActiveHoldsError,
)

from app.middleware.rate_limiter import limiter
from app.middleware.anti_bot import anti_bot
from app.middleware.waiting_room_guard import check_waiting_room_access
from app.services.idempotency import idempotency_service

router = APIRouter()


async def get_current_user_id(
    user_id: int = Query(..., description="User ID (TODO: replace with JWT auth)")
) -> int:
    return user_id


@router.post("/bookings", response_model=BookingResponse, status_code=201)
@limiter.limit("10/minute")
async def create_booking(
    request: Request,
    booking_data: BookingCreate,
    user_id: int = Depends(get_current_user_id),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    waiting_room_token: Optional[str] = Header(None, alias="X-Waiting-Room-Token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new booking with HOLD status

    Protected by:
    - Rate limiting: Max 10 bookings/minute
    - Anti-bot: Max 10 attempts/hour per user
    - Idempotency: Safe to retry with same key
    - Waiting Room: Must have valid token if enabled
    
    Headers:
    - X-Idempotency-Key: Optional UUID for safe retries
    - X-Waiting-Room-Token: Required if waiting room is enabled
    """
    
    # Check waiting room access
    await check_waiting_room_access(request, booking_data.event_id, waiting_room_token)
    
    # Anti-bot protection
    await anti_bot.check_booking_pattern(user_id=user_id)
    
    # ADD IDEMPOTENCY HANDLING (starts here)
    if not idempotency_key:
        idempotency_key = idempotency_service.generate_key(
            user_id=user_id,
            operation="create_booking",
            params={
                "event_id": booking_data.event_id,
                "seat_ids": tuple(sorted(booking_data.seat_ids))
            }
        )
    
    # Check if already processed
    existing_result = await idempotency_service.check_operation(idempotency_key)
    if existing_result:
        return BookingResponse(**existing_result)
    
    # Acquire lock
    lock_acquired = await idempotency_service.lock_operation(idempotency_key, ttl=30)
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="Booking operation already in progress. Please wait."
        )
    
    try:
        booking = await BookingService.create_hold(
            db=db,
            user_id=user_id,
            event_id=booking_data.event_id,
            seat_ids=booking_data.seat_ids,
        )
        
        response = BookingResponse.from_booking(booking)
        
        # Store result for idempotency
        await idempotency_service.store_result(
            idempotency_key, 
            response.model_dump(mode="json")
        )
        
        return response
        
    except EventNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SeatsUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except TooManyActiveHoldsError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except BookingServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await idempotency_service.release_lock(idempotency_key)


@router.post("/bookings/{booking_id}/confirm", response_model=BookingResponse)
@limiter.limit("10/minute")  # ✅ ADD THIS
async def confirm_booking(
    request: Request,  # ✅ ADD THIS PARAMETER
    booking_id: int,
    confirm_data: BookingConfirm,
    user_id: int = Depends(get_current_user_id),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),  # ✅ ADD THIS
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm a HOLD booking
    
    Idempotent: Safe to retry if payment processing fails
    """
    if not idempotency_key:
        idempotency_key = idempotency_service.generate_key(
            user_id=user_id,
            operation="confirm_booking",
            params={
                "booking_id": booking_id,
                "payment_id": confirm_data.payment_id
            }
        )
    
    existing_result = await idempotency_service.check_operation(idempotency_key)
    if existing_result:
        return BookingResponse(**existing_result)
    
    lock_acquired = await idempotency_service.lock_operation(idempotency_key)
    if not lock_acquired:
        raise HTTPException(409, "Confirmation already in progress")
    
    try:
        booking = await BookingService.confirm_booking(
            db=db,
            booking_id=booking_id,
            user_id=user_id,
            payment_id=confirm_data.payment_id,
        )
        
        response = BookingResponse.from_booking(booking)

        await idempotency_service.store_result(
            idempotency_key,
            response.model_dump(mode="json")
        )
        
        return response
        
    except BookingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BookingExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except BookingServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await idempotency_service.release_lock(idempotency_key)


@router.delete("/bookings/{booking_id}", response_model=BookingResponse)
@limiter.limit("10/minute")
async def cancel_booking(
    request: Request,
    booking_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a booking"""
    try:
        booking = await BookingService.cancel_booking(
            db=db,
            booking_id=booking_id,
            user_id=user_id,
        )
        return BookingResponse.from_booking(booking)
        
    except BookingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BookingServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/bookings", response_model=BookingListResponse)
@limiter.limit("30/minute")
async def list_user_bookings(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    status: Optional[BookingStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all bookings for the current user"""
    try:
        bookings = await BookingService.get_user_bookings(
            db=db, 
            user_id=user_id, 
            status=status
        )
        
        return BookingListResponse(
            bookings=[BookingResponse.from_booking(b) for b in bookings],
            total=len(bookings),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
@limiter.limit("60/minute")
async def get_booking(
    request: Request,
    booking_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific booking by ID"""
    try:
        booking = await BookingService.get_booking_by_id(
            db=db, 
            booking_id=booking_id, 
            user_id=user_id
        )
        
        if not booking:
            raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        
        return BookingResponse.from_booking(booking)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
