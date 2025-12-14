"""
WebSocket API Route

Handles:
- Real-time auction updates via WebSocket
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.infrastructure.pubsub import get_pubsub_manager

# Create router
router = APIRouter(tags=["websockets"])


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================
@router.websocket("/ws/{auction_id}")
async def websocket_endpoint(websocket: WebSocket, auction_id: int):
    """
    WebSocket endpoint for real-time auction updates
    
    Uses Redis Pub/Sub - scales across multiple servers
    
    Args:
        websocket: WebSocket connection
        auction_id: Auction to subscribe to
    """
    pubsub = get_pubsub_manager()
    await pubsub.add_connection(websocket, auction_id)
    
    try:
        # Send welcome message
        await pubsub.send_personal_message(websocket, {
            "type": "CONNECTED",
            "auction_id": auction_id,
            "message": f"Connected to auction {auction_id}",
            "viewers": pubsub.get_connection_count(auction_id)
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            
            # Echo for ping/pong
            await pubsub.send_personal_message(websocket, {
                "type": "PONG",
                "message": "Connection alive"
            })
    
    except WebSocketDisconnect:
        pubsub.remove_connection(websocket, auction_id)
        print(f"🔌 Client disconnected from auction {auction_id}")
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        pubsub.remove_connection(websocket, auction_id)