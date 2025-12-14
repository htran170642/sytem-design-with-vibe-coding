"""
WebSocket connection manager
"""
from fastapi import WebSocket
from typing import Dict
from datetime import datetime


class WebSocketManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Store active connections: user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, user_id: int, websocket: WebSocket):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"✓ User {user_id} connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, user_id: int):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"✗ User {user_id} disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, user_id: int, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                return True
            except:
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast(self, message: dict, exclude_user_id: int = None):
        """Broadcast message to all connected users"""
        for user_id, connection in list(self.active_connections.items()):
            if user_id != exclude_user_id:
                try:
                    await connection.send_json(message)
                except:
                    self.disconnect(user_id)
    
    def is_online(self, user_id: int) -> bool:
        """Check if user is online"""
        return user_id in self.active_connections
    
    def get_online_count(self) -> int:
        """Get number of online users"""
        return len(self.active_connections)


# Global instance
ws_manager = WebSocketManager()