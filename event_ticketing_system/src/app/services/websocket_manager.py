"""
WebSocket connection manager with token registration
"""
from typing import Dict, List
from fastapi import WebSocket
import logging
import time

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.waiting_room_tokens: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, event_id: int):
        await websocket.accept()
        
        if event_id not in self.active_connections:
            self.active_connections[event_id] = []
        
        self.active_connections[event_id].append(websocket)
        logger.info(f"✅ WebSocket connected to event {event_id}")
    
    def disconnect(self, websocket: WebSocket, event_id: int):
        if event_id in self.active_connections:
            if websocket in self.active_connections[event_id]:
                self.active_connections[event_id].remove(websocket)
        
        # Remove from waiting room tokens
        tokens_to_remove = [
            token for token, ws in self.waiting_room_tokens.items() 
            if ws == websocket
        ]
        for token in tokens_to_remove:
            del self.waiting_room_tokens[token]
            logger.info(f"🗑️ Removed token {token[:8]}...")
        
        logger.info(f"❌ WebSocket disconnected from event {event_id}")
    
    async def handle_message(self, websocket: WebSocket, event_id: int, message: dict):
        """Handle incoming messages from client"""
        msg_type = message.get('type')
        
        logger.info(f"📨 Received message: type={msg_type}, event={event_id}")
        
        if msg_type == 'register_waiting_room':
            token = message.get('token')
            if token:
                self.waiting_room_tokens[token] = websocket
                logger.info(f"✅ Registered token {token[:8]}... for event {event_id}")
                logger.info(f"📊 Total registered tokens: {len(self.waiting_room_tokens)}")
                
                await websocket.send_json({
                    "type": "registration_confirmed",
                    "token": token[:8] + "...",
                    "message": "Token registered successfully"
                })
            else:
                logger.warning(f"⚠️ Registration message missing token!")
        
        elif msg_type == 'ping':
            await websocket.send_json({
                "type": "pong",
                "timestamp": time.time()
            })
        
        else:
            logger.warning(f"❓ Unknown message type: {msg_type}")
    
    async def send_admission_notification(self, event_id: int, token: str):
        """Notify specific user they've been admitted"""
        logger.info(f"🔔 Attempting to send admission to token {token[:8]}...")
        logger.info(f"📊 Currently registered tokens: {list(self.waiting_room_tokens.keys())[:5]}")  # Show first 5
        
        websocket = self.waiting_room_tokens.get(token)
        
        if websocket:
            message = {
                "type": "admitted",
                "token": token,
                "message": "You have been admitted!",
                "timestamp": time.time()
            }
            
            try:
                await websocket.send_json(message)
                logger.info(f"✅ Sent admission notification to {token[:8]}... to browser")
            except Exception as e:
                logger.error(f"❌ Failed to send to {token[:8]}: {e}")
        else:
            logger.warning(f"⚠️ No WebSocket found for token {token[:8]}")
            logger.warning(f"⚠️ Available tokens: {[t[:8] + '...' for t in self.waiting_room_tokens.keys()]}")
    
    async def broadcast_to_event(self, event_id: int, message: dict):
        """Broadcast message to all connections for an event"""
        if event_id not in self.active_connections:
            return
        
        disconnected = []
        
        for websocket in self.active_connections[event_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending: {e}")
                disconnected.append(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket, event_id)
    
    async def broadcast_seat_update(self, event_id: int, seat_ids: list, status: str, booking_id: int):
        message = {
            "type": "seat_update",
            "event_id": event_id,
            "seat_ids": seat_ids,
            "status": status,
            "booking_id": booking_id,
            "timestamp": time.time()
        }
        
        await self.broadcast_to_event(event_id, message)
        logger.info(f"📡 Broadcast: {len(seat_ids)} seats → {status}")
    
    async def broadcast_booking_expiry(self, event_id: int, booking_id: int, seat_ids: list):
        message = {
            "type": "booking_expired",
            "event_id": event_id,
            "booking_id": booking_id,
            "seat_ids": seat_ids,
            "status": "AVAILABLE",
            "timestamp": time.time()
        }
        
        await self.broadcast_to_event(event_id, message)
        logger.info(f"📡 Broadcast: booking {booking_id} expired")


manager = ConnectionManager()
