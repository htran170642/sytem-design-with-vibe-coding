"""
WebSocket Manager Service for real-time seat updates
Manages WebSocket connections and broadcasts seat status changes
"""
from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    
    Connections are grouped by event_id so we can broadcast
    seat updates only to users viewing that specific event
    """
    
    def __init__(self):
        # event_id -> list of WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # WebSocket -> event_id (for cleanup)
        self.connection_to_event: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, event_id: int):
        """
        Accept a new WebSocket connection for an event
        
        Args:
            websocket: WebSocket connection
            event_id: Event ID the user is viewing
        """
        await websocket.accept()
        
        if event_id not in self.active_connections:
            self.active_connections[event_id] = []
        
        self.active_connections[event_id].append(websocket)
        self.connection_to_event[websocket] = event_id
        
        print(f"✅ WebSocket connected for event {event_id} "
              f"(total: {len(self.active_connections[event_id])})")
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection
        
        Args:
            websocket: WebSocket connection to remove
        """
        if websocket not in self.connection_to_event:
            return
        
        event_id = self.connection_to_event[websocket]
        
        if event_id in self.active_connections:
            self.active_connections[event_id].remove(websocket)
            
            # Clean up empty event lists
            if not self.active_connections[event_id]:
                del self.active_connections[event_id]
        
        del self.connection_to_event[websocket]
        
        remaining = len(self.active_connections.get(event_id, []))
        print(f"🔌 WebSocket disconnected from event {event_id} "
              f"(remaining: {remaining})")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection
        
        Args:
            message: Message dict to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"❌ Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_event(self, message: dict, event_id: int):
        """
        Broadcast a message to all connections watching an event
        
        Args:
            message: Message dict to broadcast
            event_id: Event ID to broadcast to
        """
        if event_id not in self.active_connections:
            return  # No one watching this event
        
        connections = self.active_connections[event_id].copy()
        dead_connections = []
        
        # Send to all connections concurrently
        tasks = []
        for connection in connections:
            try:
                tasks.append(connection.send_json(message))
            except Exception:
                dead_connections.append(connection)
        
        # Wait for all sends to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)
        
        active_count = len(self.active_connections.get(event_id, []))
        print(f"📡 Broadcast to event {event_id}: {active_count} recipients")
    
    async def broadcast_seat_update(
        self,
        event_id: int,
        seat_ids: List[int],
        new_status: str,
        booking_id: int = None
    ):
        """
        Broadcast seat status changes to all viewers
        
        Args:
            event_id: Event ID
            seat_ids: List of seat IDs that changed
            new_status: New status (AVAILABLE, HOLD, BOOKED)
            booking_id: Related booking ID (optional)
        """
        message = {
            "type": "seat_update",
            "event_id": event_id,
            "seat_ids": seat_ids,
            "status": new_status,
            "booking_id": booking_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.broadcast_to_event(message, event_id)
    
    async def broadcast_booking_expiry(self, event_id: int, booking_id: int, seat_ids: List[int]):
        """
        Broadcast when a booking expires and seats become available
        
        Args:
            event_id: Event ID
            booking_id: Expired booking ID
            seat_ids: Seats that became available
        """
        message = {
            "type": "booking_expired",
            "event_id": event_id,
            "booking_id": booking_id,
            "seat_ids": seat_ids,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.broadcast_to_event(message, event_id)
    
    def get_connection_count(self, event_id: int = None) -> int:
        """
        Get number of active connections
        
        Args:
            event_id: If provided, count for specific event. Otherwise total.
            
        Returns:
            Connection count
        """
        if event_id:
            return len(self.active_connections.get(event_id, []))
        
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()
