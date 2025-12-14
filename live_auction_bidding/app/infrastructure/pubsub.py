"""
Redis Pub/Sub Manager for Scalable WebSockets

Key Concepts:

1. Publish/Subscribe Pattern:
   - Publishers send messages to channels
   - Subscribers listen to channels
   - All subscribers get every message

2. Channels:
   - Named message streams
   - Example: "auction:123", "auction:456"
   - Subscribe to specific channels

3. Decoupling:
   - Publishers don't know who's listening
   - Subscribers don't know who's publishing
   - Perfect for distributed systems

Architecture:
┌──────────────┐
│  Publisher   │ (Worker, API)
│              │
└──────┬───────┘
       │ PUBLISH "auction:123" {"type": "NEW_BID", ...}
       ↓
┌──────────────────────────────────────┐
│          Redis Pub/Sub               │
│                                      │
│  Channel: "auction:123"              │
│  Message: {"type": "NEW_BID", ...}  │
└──────┬────────────────────┬──────────┘
       │                    │
       ↓                    ↓
┌──────────────┐    ┌──────────────┐
│ Subscriber 1 │    │ Subscriber 2 │ (Servers)
│ (Server 1)   │    │ (Server 2)   │
└──────┬───────┘    └──────┬───────┘
       │                    │
       ↓                    ↓
   WebSocket           WebSocket
   Clients 1-10K       Clients 10K-20K
"""

import asyncio
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket
import redis.asyncio as redis

from app.core.config import get_settings

class PubSubManager:
    """
    Manages Redis Pub/Sub for WebSocket broadcasting
    
    Benefits:
    - Scale WebSocket connections across multiple servers
    - Workers can publish from anywhere
    - Servers can be added/removed dynamically
    - No shared memory needed
    
    Usage:
        # Server 1:
        manager = PubSubManager()
        await manager.connect()
        await manager.subscribe_to_auction(123)
        # Receives all messages for auction 123
        
        # Worker (anywhere):
        await manager.publish_to_auction(123, {"type": "NEW_BID"})
        # Server 1 receives and broadcasts to its WebSocket clients
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize Pub/Sub manager
        
        Args:
            redis_url: Redis connection URL
        """
        
        if redis_url is None:
            settings = get_settings()
            redis_url = settings.REDIS_URL

        self.redis_url = redis_url
        self.redis = None           # Redis client for publishing
        self.pubsub = None          # Redis Pub/Sub client for subscribing
        
        # Local WebSocket connections (per server)
        # auction_id -> Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        
        # Subscribed channels (per server)
        self.subscriptions: Set[str] = set()
        
        # Statistics
        self.messages_received = 0
        self.messages_published = 0
    
    async def connect(self):
        """
        Initialize Redis connection and Pub/Sub
        
        This creates TWO Redis connections:
        1. Regular client for PUBLISH commands
        2. Pub/Sub client for SUBSCRIBE and listening
        
        Why two connections?
        - Pub/Sub connection is blocking (listens constantly)
        - Regular connection for other Redis operations
        """
        print("🔌 [PubSub] Connecting to Redis...")
        
        # Connection 1: For publishing messages
        self.redis = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Connection 2: For subscribing to channels
        self.pubsub = self.redis.pubsub()
        
        # Start listening for messages
        asyncio.create_task(self._listen_loop())
        
        print("✅ [PubSub] Connected to Redis")
    
    async def disconnect(self):
        """Clean shutdown"""
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        if self.redis:
            await self.redis.close()
        
        print("🔌 [PubSub] Disconnected from Redis")
    
    def _channel_name(self, auction_id: int) -> str:
        """
        Generate channel name for auction
        
        Pattern: "auction:{auction_id}"
        Example: "auction:123"
        
        Why this pattern?
        - Clear naming (easy to debug)
        - Namespaced (won't conflict)
        - Easy to subscribe to all auctions: "auction:*"
        """
        return f"auction:{auction_id}"
    
    async def subscribe_to_auction(self, auction_id: int):
        """
        Subscribe to auction updates
        
        This tells Redis: "Send me all messages published to auction:123"
        
        Flow:
        1. Generate channel name
        2. Subscribe to channel
        3. Start receiving messages (in _listen_loop)
        
        Args:
            auction_id: Which auction to listen to
        """
        channel = self._channel_name(auction_id)
        
        if channel not in self.subscriptions:
            await self.pubsub.subscribe(channel)
            self.subscriptions.add(channel)
            
            print(f"📡 [PubSub] Subscribed to {channel}")
    
    async def unsubscribe_from_auction(self, auction_id: int):
        """
        Unsubscribe from auction updates
        
        Call this when:
        - No more WebSocket clients for this auction
        - Auction ended
        - Cleanup
        """
        channel = self._channel_name(auction_id)
        
        if channel in self.subscriptions:
            await self.pubsub.unsubscribe(channel)
            self.subscriptions.remove(channel)
            
            print(f"📡 [PubSub] Unsubscribed from {channel}")
    
    async def publish_to_auction(self, auction_id: int, message: dict):
        """
        Publish message to auction channel
        
        This is called by:
        - Workers (after processing bid)
        - API servers (for immediate feedback)
        
        Flow:
        1. Generate channel name
        2. Serialize message to JSON
        3. PUBLISH to Redis
        4. ALL subscribed servers receive message
        5. Each server broadcasts to its WebSocket clients
        
        Args:
            auction_id: Which auction
            message: Data to broadcast
        
        Example:
            >>> await manager.publish_to_auction(123, {
            >>>     "type": "NEW_BID",
            >>>     "bid_amount": 1500.00,
            >>>     "user_id": 456
            >>> })
            # All servers subscribed to auction:123 receive this
        """
        channel = self._channel_name(auction_id)
        
        # Serialize to JSON
        message_json = json.dumps(message)
        
        # PUBLISH to Redis
        # Returns number of subscribers who received the message
        num_subscribers = await self.redis.publish(channel, message_json)
        
        self.messages_published += 1
        
        print(f"📢 [PubSub] Published to {channel} "
              f"({num_subscribers} subscribers)")
    
    async def _listen_loop(self):
        """
        Background task that listens for Pub/Sub messages
        
        This runs continuously, waiting for messages from Redis.
        When a message arrives, it broadcasts to local WebSocket clients.
        
        Flow:
        1. Wait for message from Redis (blocking)
        2. Parse message
        3. Extract auction_id
        4. Broadcast to local WebSocket clients
        5. Repeat forever
        
        Message Types:
        - "subscribe": Subscription confirmed
        - "unsubscribe": Unsubscription confirmed
        - "message": Actual data message (this is what we want!)
        """
        print("👂 [PubSub] Listen loop started")
        
        try:
            # Listen forever
            async for message in self.pubsub.listen():
                
                # Ignore subscription confirmations
                if message['type'] not in ['message']:
                    continue
                
                try:
                    # Parse message data
                    channel = message['channel']
                    data_json = message['data']
                    data = json.loads(data_json)
                    
                    # Extract auction_id from channel name
                    # Channel: "auction:123" → auction_id: 123
                    auction_id = int(channel.split(':')[1])
                    
                    self.messages_received += 1
                    
                    print(f"📨 [PubSub] Received message on {channel}")
                    
                    # Broadcast to local WebSocket clients
                    await self._broadcast_to_local_websockets(auction_id, data)
                
                except Exception as e:
                    print(f"❌ [PubSub] Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
        
        except Exception as e:
            print(f"❌ [PubSub] Listen loop error: {e}")
            import traceback
            traceback.print_exc()
    
    async def _broadcast_to_local_websockets(self, auction_id: int, message: dict):
        """
        Broadcast message to WebSocket clients connected to THIS server
        
        This is the LOCAL broadcast (not Redis Pub/Sub)
        
        Flow:
        1. Get all WebSocket connections for this auction (on this server)
        2. Send message to each connection
        3. Remove disconnected connections
        
        Args:
            auction_id: Which auction
            message: Data to send
        """
        if auction_id not in self.active_connections:
            return
        
        connections = self.active_connections[auction_id].copy()
        
        print(f"📢 [PubSub] Broadcasting to {len(connections)} "
              f"local WebSocket clients")
        
        disconnected = set()
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"⚠️  [PubSub] WebSocket send error: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.remove_connection(websocket, auction_id)
    
    async def add_connection(self, websocket: WebSocket, auction_id: int):
        """
        Add WebSocket connection to local manager
        
        Flow:
        1. Accept WebSocket connection
        2. Add to local connections set
        3. Subscribe to Redis channel (if not already)
        
        Args:
            websocket: WebSocket connection
            auction_id: Which auction
        """
        # Accept connection
        await websocket.accept()
        
        # Add to local connections
        if auction_id not in self.active_connections:
            self.active_connections[auction_id] = set()
        
        self.active_connections[auction_id].add(websocket)
        
        # Subscribe to Redis channel
        await self.subscribe_to_auction(auction_id)
        
        print(f"🔌 [PubSub] WebSocket connected to auction {auction_id} "
              f"(local: {len(self.active_connections[auction_id])})")
    
    def remove_connection(self, websocket: WebSocket, auction_id: int):
        """
        Remove WebSocket connection
        
        Flow:
        1. Remove from local connections
        2. If no more local connections, unsubscribe from Redis
        
        Args:
            websocket: WebSocket to remove
            auction_id: Which auction
        """
        if auction_id in self.active_connections:
            self.active_connections[auction_id].discard(websocket)
            
            # Clean up empty sets
            if len(self.active_connections[auction_id]) == 0:
                del self.active_connections[auction_id]
                
                # Unsubscribe from Redis (no more local clients)
                asyncio.create_task(
                    self.unsubscribe_from_auction(auction_id)
                )
            
            print(f"🔌 [PubSub] WebSocket disconnected from auction {auction_id}")
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Send message to specific WebSocket client
        
        This is NOT broadcasted - only goes to one client
        
        Use for:
        - Connection confirmation
        - Personal notifications
        - Error messages
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"⚠️  [PubSub] Personal message error: {e}")
    
    def get_connection_count(self, auction_id: int) -> int:
        """
        Get number of LOCAL WebSocket connections
        
        Note: This only counts connections on THIS server!
        Other servers may have their own connections.
        
        Returns:
            Number of local connections
        """
        if auction_id not in self.active_connections:
            return 0
        return len(self.active_connections[auction_id])
    
    def get_stats(self) -> dict:
        """
        Get Pub/Sub statistics
        
        Useful for monitoring
        
        Returns:
            Dict with stats
        """
        return {
            "subscriptions": len(self.subscriptions),
            "messages_received": self.messages_received,
            "messages_published": self.messages_published,
            "active_auctions": len(self.active_connections),
            "total_connections": sum(
                len(conns) for conns in self.active_connections.values()
            )
        }


# ============================================================================
# Global instance (singleton)
# ============================================================================
_pubsub_instance = None

def get_pubsub_manager() -> PubSubManager:
    """
    Get global Pub/Sub manager instance
    
    Returns:
        PubSubManager instance
    """
    global _pubsub_instance
    
    if _pubsub_instance is None:
        _pubsub_instance = PubSubManager()
    
    return _pubsub_instance