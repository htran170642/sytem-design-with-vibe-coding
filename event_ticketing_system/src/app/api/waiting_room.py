"""
Waiting Room API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.waiting_room import waiting_room_service
from app.services.background_tasks import task_manager

from app.core.config import settings

router = APIRouter()


@router.post("/events/{event_id}/waiting-room/enable")
async def enable_waiting_room(
    event_id: int,
    max_concurrent: int = Query(1000, description="Max concurrent users"),
    session_duration: int = Query(300, description="Session duration in seconds")
):
    """
    Enable waiting room for an event
    
    Use this when expecting high traffic (e.g., Taylor Swift concert)
    """
    if session_duration is None:
        session_duration = settings.WAITING_ROOM_SESSION_DURATION
    
    await waiting_room_service.enable_waiting_room(
        event_id=event_id,
        max_concurrent=max_concurrent,
        session_duration=session_duration
    )
    
    # ✅ Start auto-admission worker
    task_name = f"waiting_room_worker_{event_id}"
    task_manager.start_task(
        task_name,
        waiting_room_service.start_auto_admission_worker,
        event_id
    )
    
    return {
        "message": f"Waiting room enabled for event {event_id}",
        "max_concurrent_users": max_concurrent,
        "session_duration_seconds": session_duration
    }


@router.post("/events/{event_id}/waiting-room/disable")
async def disable_waiting_room(event_id: int):
    """Disable waiting room for an event"""
    await waiting_room_service.disable_waiting_room(event_id)
    waiting_room_service.stop_auto_admission_worker(event_id)
    return {
        "message": f"Waiting room disabled for event {event_id}"
    }


@router.post("/events/{event_id}/waiting-room/join")
async def join_waiting_room(
    event_id: int,
    user_id: int = Query(..., description="User ID")
):
    """
    Join the waiting room queue
    
    Returns:
    - token: Unique token for this session
    - position: Position in queue
    - estimated_wait_seconds: Estimated wait time
    """
    result = await waiting_room_service.join_queue(
        event_id=event_id,
        user_id=user_id
    )
    
    return result


@router.get("/events/{event_id}/waiting-room/status")
async def check_waiting_room_status(
    event_id: int,
    token: str = Query(..., description="Waiting room token")
):
    """
    Check status in waiting room
    
    Poll this endpoint every 5 seconds to check if admitted
    """
    result = await waiting_room_service.check_status(
        event_id=event_id,
        token=token
    )
    
    return result


@router.get("/events/{event_id}/waiting-room/stats")
async def get_waiting_room_stats(event_id: int):
    """
    Get waiting room statistics
    
    Returns queue size, active sessions, slots available
    """
    stats = await waiting_room_service.get_stats(event_id)
    return stats
