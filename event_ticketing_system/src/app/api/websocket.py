"""
WebSocket API for real-time seat updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.services import manager

router = APIRouter()


@router.websocket("/events/{event_id}")
async def websocket_event_seats(
    websocket: WebSocket,
    event_id: int,
    user_id: Optional[int] = Query(None, description="User ID (optional)")
):
    """
    WebSocket endpoint for real-time seat updates
    
    **Connection URL**: ws://localhost:8000/ws/events/{event_id}
    
    **What you receive:**
    - Real-time seat status changes (AVAILABLE, HOLD, BOOKED)
    - Booking expiration notifications
    - Other users' booking activities
    
    **Message format:**
```json
    {
        "type": "seat_update",
        "event_id": 1,
        "seat_ids": [1, 2, 3],
        "status": "HOLD",
        "booking_id": 42,
        "timestamp": 1702345678.123
    }
```
    
    Or for expiry:
```json
    {
        "type": "booking_expired",
        "event_id": 1,
        "booking_id": 42,
        "seat_ids": [1, 2, 3],
        "timestamp": 1702345678.123
    }
```
    """
    # Accept connection
    await manager.connect(websocket, event_id)
    
    try:
        # Send welcome message
        await manager.send_personal_message(
            {
                "type": "connected",
                "event_id": event_id,
                "message": f"Connected to event {event_id} updates",
                "user_id": user_id
            },
            websocket
        )
        
        # Keep connection alive and listen for messages
        while True:
            # Receive messages from client (if any)
            data = await websocket.receive_text()
            
            # Echo back for now (can add ping/pong logic)
            await manager.send_personal_message(
                {
                    "type": "echo",
                    "data": data
                },
                websocket
            )
            print(f"↩️ Echoed message to client on event {event_id}: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected from event {event_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
