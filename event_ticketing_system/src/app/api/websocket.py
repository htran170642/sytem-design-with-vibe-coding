"""
WebSocket endpoint for real-time updates
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/events/{event_id}")
async def websocket_endpoint(websocket: WebSocket, event_id: int):
    """
    WebSocket endpoint for real-time event updates
    """
    await manager.connect(websocket, event_id)
    
    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "event_id": event_id,
        "message": f"Connected to event {event_id} updates"
    })
    
    try:
        while True:
            # ✅ Receive and handle messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                logger.info(f"📨 Received message: {message}")
                await manager.handle_message(websocket, event_id, message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, event_id)
        logger.info(f"Client disconnected from event {event_id}")
