# websocket_manager.py
"""
WebSocket manager for real-time auction updates
"""
from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio

class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    """
    
    def __init__(self):
        # auction_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, auction_id: int):
        """Connect a client to an auction's updates"""
        await websocket.accept()
        
        if auction_id not in self.active_connections:
            self.active_connections[auction_id] = set()
        
        self.active_connections[auction_id].add(websocket)
        
        print(f"🔌 Client connected to auction {auction_id}")
        print(f"   Total viewers: {len(self.active_connections[auction_id])}")
    
    def disconnect(self, websocket: WebSocket, auction_id: int):
        """Disconnect a client from an auction"""
        if auction_id in self.active_connections:
            self.active_connections[auction_id].discard(websocket)
            
            # Clean up empty sets
            if len(self.active_connections[auction_id]) == 0:
                del self.active_connections[auction_id]
            
            print(f"🔌 Client disconnected from auction {auction_id}")
    
    async def broadcast(self, auction_id: int, message: dict):
        """
        Broadcast message to all clients watching this auction
        """
        if auction_id not in self.active_connections:
            return
        
        # Get all connections for this auction
        connections = self.active_connections[auction_id].copy()
        
        print(f"📢 Broadcasting to {len(connections)} clients on auction {auction_id}")
        
        # Send to all connections
        disconnected = set()
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"⚠️  Error sending to client: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, auction_id)
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"⚠️  Error sending personal message: {e}")
    
    def get_viewer_count(self, auction_id: int) -> int:
        """Get number of viewers for an auction"""
        if auction_id not in self.active_connections:
            return 0
        return len(self.active_connections[auction_id])


# Global WebSocket manager
manager = ConnectionManager()