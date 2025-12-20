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
        self._workers_running: Dict[int, bool] = {}
    
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
        
        # Get total queue size
        queue_size = await self.redis.redis.zcard(queue_key) or 0
        
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
            f"User {user_id}: queue_size={queue_size}, position={position}, active={active_count}, "
            f"slots={slots_available}, batch={batch_number}, wait={estimated_wait}s"
        )
        
        return {
            "token": token,
            "position": position + 1 if position is not None else 1,
            "estimated_wait_seconds": int(estimated_wait),
            "status": "queued"
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
        
        # actively set expiry on active set membership
        await self.redis.redis.expire(active_key, session_duration)
        
        logger.info(f"✅ User admitted to event {event_id} with token {token} with TTL {session_duration}")
    
    async def get_stats(self, event_id: int) -> Dict:
        """Get waiting room statistics"""
        
        # ✅ Check if waiting room is enabled first
        is_enabled = await self.is_enabled(event_id)
        if not is_enabled:
            return None

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
                
    async def _process_queue(self, event_id: int):
        """
        Automatically admit users from queue when slots available
        """
        queue_key = f"waiting_room:{event_id}:queue"
        active_key = f"waiting_room:{event_id}:active"
        
        # Get config
        config = await self.redis.get(f"waiting_room:{event_id}:config")
        if not config:
            logger.warning(f"No waiting room config found for event {event_id}")
            return
        
        max_concurrent = config.get("max_concurrent_users", 1000)
        
        # Get current active count
        active_count = await self.redis.redis.scard(active_key) or 0
        
        # Calculate how many we can admit
        
        slots_available = max_concurrent - active_count
        
        if slots_available <= 0:
            logger.info(f"No slots available for event {event_id}, max_concurrent={max_concurrent}, active={active_count}")
            return  # No slots, nothing to do
        
        # Get next N users from queue
        tokens_to_admit = await self.redis.redis.zrange(
            queue_key, 
            0, 
            slots_available - 1  # Get first N tokens
        )
        
        if not tokens_to_admit:
            logger.info(f"No users in queue to admit for event {event_id}")
            return  # Queue empty
        
        logger.info(f"🎫 Auto-admitting {len(tokens_to_admit)} users to event {event_id}")
        
        # Admit each user
        for token in tokens_to_admit:
            await self._admit_user(event_id, token)
            
            # ✅ Notify via WebSocket
            from app.services.websocket_manager import manager
            await manager.send_admission_notification(event_id, token)
            
    async def start_auto_admission_worker(self, event_id: int):
        """
        Background worker that automatically admits users when slots available
        Runs every 5 seconds
        """
        worker_key = f"auto_admission_worker_{event_id}"
        
        if self._workers_running.get(event_id, False):
            logger.warning(f"Auto-admission worker already running for event {event_id}")
            return
        
        self._workers_running[event_id] = True
        logger.info(f"🚀 Starting auto-admission worker for event {event_id}")
        
        await asyncio.sleep(5)

        try:
            while self._workers_running.get(event_id, False):
                try:
                    # Check if waiting room is still enabled
                    is_enabled = await self.is_enabled(event_id)
                    if not is_enabled:
                        logger.info(f"Waiting room disabled for event {event_id}, stopping worker")
                        break
                    
                    # Process queue
                    await self._process_queue(event_id)

                    # Wait 5 seconds before next check
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error in auto-admission worker for event {event_id}: {e}")
                    await asyncio.sleep(5)  # Continue after error
                    
        finally:
            self._workers_running[event_id] = False
            logger.info(f"🛑 Auto-admission worker stopped for event {event_id}")
    
    def stop_auto_admission_worker(self, event_id: int):
        """Stop auto-admission worker for an event"""
        self._workers_running[event_id] = False
        logger.info(f"🛑 Stopping auto-admission worker for event {event_id}")


# Global instance
waiting_room_service = WaitingRoomService()
