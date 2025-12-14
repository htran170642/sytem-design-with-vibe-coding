"""
Virtual Waiting Room for handling surge traffic
Queues users during peak load to prevent system overload
"""
import asyncio
import time
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum
import uuid
import logging
import math

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class WaitingRoomStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


@dataclass
class WaitingRoomConfig:
    """Configuration for a waiting room"""
    event_id: int
    max_concurrent_users: int = 1000
    session_duration_seconds: int = 300
    queue_enabled: bool = True


class WaitingRoomService:
    """Manages virtual waiting room for high-demand events"""
    
    def __init__(self):
        self.redis = redis_client
    
    async def is_enabled(self, event_id: int) -> bool:
        """Check if waiting room is enabled for event"""
        key = f"waiting_room:{event_id}:status"
        status = await self.redis.get(key)
        return status == WaitingRoomStatus.ACTIVE.value if status else False
    
    async def enable_waiting_room(
        self,
        event_id: int,
        max_concurrent: int = 1000,
        session_duration: int = 300
    ):
        """Enable waiting room for an event"""
        config_key = f"waiting_room:{event_id}:config"
        status_key = f"waiting_room:{event_id}:status"
        
        config = {
            "max_concurrent_users": max_concurrent,
            "session_duration_seconds": session_duration,
            "enabled_at": time.time()
        }
        
        await self.redis.set(config_key, config)
        await self.redis.set(status_key, WaitingRoomStatus.ACTIVE.value)
        
        logger.info(f"✅ Waiting room enabled for event {event_id}")
    
    async def disable_waiting_room(self, event_id: int):
        """Disable waiting room for an event"""
        status_key = f"waiting_room:{event_id}:status"
        await self.redis.set(status_key, WaitingRoomStatus.INACTIVE.value)
        logger.info(f"🔴 Waiting room disabled for event {event_id}")
    
    async def join_queue(self, event_id: int, user_id: int) -> Dict:
        """Add user to waiting room queue"""
        # Generate unique token
        token = str(uuid.uuid4())
        
        # Add to queue (sorted set by timestamp)
        queue_key = f"waiting_room:{event_id}:queue"
        timestamp = time.time()
        
        await self.redis.redis.zadd(queue_key, {token: timestamp})
        
        # Store user info
        user_key = f"waiting_room:{event_id}:user:{token}"
        await self.redis.set(user_key, {"user_id": user_id, "joined_at": timestamp}, ttl=3600)
        
        # Get 0-indexed position in queue
        position = await self.redis.redis.zrank(queue_key, token)
        
        # Get active users count
        active_key = f"waiting_room:{event_id}:active"
        active_count = await self.redis.redis.scard(active_key) or 0
        
        # Get config
        config = await self.redis.get(f"waiting_room:{event_id}:config")
        max_concurrent = config.get("max_concurrent_users", 1000) if config else 1000
        session_duration = config.get("session_duration_seconds", 300) if config else 300
        
        # Calculate available slots
        slots_available = max(0, max_concurrent - active_count)
        
        # ✅ Calculate which batch the user is in
        if position < slots_available:
            # User is in the immediate batch (can enter now)
            batch_number = 0
        else:
            # User is in a future batch
            users_after_slots = position - slots_available
            batch_number = (users_after_slots // max_concurrent) + 1
        
        estimated_wait = batch_number * session_duration
        
        logger.info(
            f"User {user_id}: position={position}, active={active_count}, "
            f"slots={slots_available}, batch={batch_number}, wait={estimated_wait}s"
        )
        
        return {
            "token": token,
            "position": position + 1 if position is not None else 1,
            "estimated_wait_seconds": int(estimated_wait),
            "status": "queued"
        }
    
    async def check_status(self, event_id: int, token: str) -> Dict:
        """Check user's position in queue"""
        queue_key = f"waiting_room:{event_id}:queue"
        active_key = f"waiting_room:{event_id}:active"
        
        # Check if already admitted
        is_active = await self.redis.redis.sismember(active_key, token)
        if is_active:
            return {
                "admitted": True,
                "status": "active",
                "message": "You can proceed to book tickets"
            }
        
        # Get current position
        position = await self.redis.redis.zrank(queue_key, token)
        if position is None:
            return {
                "admitted": False,
                "status": "not_found",
                "message": "Token not found in queue"
            }
        
        # Get config
        config = await self.redis.get(f"waiting_room:{event_id}:config")
        max_concurrent = config.get("max_concurrent_users", 1000) if config else 1000
        session_duration = config.get("session_duration_seconds", 300) if config else 300
        active_count = await self.redis.redis.scard(active_key) or 0
        
        # Calculate available slots
        slots_available = max_concurrent - active_count
        
        # Admit user if there are slots AND user is within available range
        if slots_available > 0 and position < slots_available:
            await self._admit_user(event_id, token)
            return {
                "admitted": True,
                "status": "admitted",
                "message": "You can now proceed to book tickets"
            }
        
        # Calculate wait time
        if position < slots_available:
            batch_number = 0
        else:
            users_after_slots = position - slots_available
            batch_number = (users_after_slots // max_concurrent) + 1
        
        estimated_wait = batch_number * session_duration
        
        return {
            "admitted": False,
            "status": "waiting",
            "position": position + 1,
            "estimated_wait_seconds": int(estimated_wait),
            "message": f"You are #{position + 1} in queue"
        }
    
    async def _admit_user(self, event_id: int, token: str):
        """Move user from queue to active session"""
        queue_key = f"waiting_room:{event_id}:queue"
        active_key = f"waiting_room:{event_id}:active"
        
        # Remove from queue
        await self.redis.redis.zrem(queue_key, token)
        
        # Add to active sessions with TTL
        config = await self.redis.get(f"waiting_room:{event_id}:config")
        session_duration = config.get("session_duration_seconds", 300) if config else 300
        
        await self.redis.redis.sadd(active_key, token)
        await self.redis.redis.expire(active_key, session_duration)
        
        logger.info(f"✅ User admitted to event {event_id} with token {token}")
    
    async def get_stats(self, event_id: int) -> Dict:
        """Get waiting room statistics"""
        queue_key = f"waiting_room:{event_id}:queue"
        active_key = f"waiting_room:{event_id}:active"
        
        queue_size = await self.redis.redis.zcard(queue_key) or 0
        active_count = await self.redis.redis.scard(active_key) or 0
        
        config = await self.redis.get(f"waiting_room:{event_id}:config")
        max_concurrent = config.get("max_concurrent_users", 1000) if config else 1000
        
        return {
            "event_id": event_id,
            "queue_size": queue_size,
            "active_sessions": active_count,
            "max_concurrent": max_concurrent,
            "slots_available": max(0, max_concurrent - active_count)
        }


# Global instance
waiting_room_service = WaitingRoomService()
