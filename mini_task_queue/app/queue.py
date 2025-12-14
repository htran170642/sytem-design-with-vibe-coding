import redis.asyncio as aioredis
from redis.asyncio import Redis
from typing import Optional
import json
from datetime import datetime

from app.config import settings
from app.models import Task, TaskStatus
from app.utils import task_to_redis, redis_to_task, create_event


class RedisQueue:
    """Redis-backed async task queue"""
    
    def __init__(self):
        self.redis: Optional[Redis] = None
        self.queue_name = settings.worker_queue_name
    
    async def connect(self):
        """Establish Redis connection pool"""
        self.redis = await aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
            password=settings.redis_password,
            encoding="utf-8",
            decode_responses=False,  # We'll handle decoding ourselves
            max_connections=50
        )
        print(f"[queue] ✅ Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    
    async def disconnect(self):
        """Close Redis connection pool"""
        if self.redis:
            await self.redis.close()
            print("✅ Disconnected from Redis")
    
    async def ping(self) -> bool:
        """Health check"""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False
        
    async def enqueue_task(self, task: Task) -> str:
        """
        Add task to queue
        
        Steps:
        1. Store task metadata in Redis hash
        2. Push task ID to Redis list (queue)
        
        Returns:
            task_id: The UUID of the enqueued task
        """
        # Store task metadata
        task_key = f"task:{task.id}"
        task_data = task_to_redis(task)
        
        await self.redis.hset(task_key, mapping=task_data)
        
        # Add to queue
        await self.redis.lpush(self.queue_name, task.id)
        
        print(f"[queue] 📥 Enqueued task {task.id} ({task.name})")
        return task.id
    
    async def pop_task(self, timeout: int = 5) -> Optional[str]:
        """
        Pop task from queue (blocking)
        
        Uses BRPOP (blocking right pop) - waits up to `timeout` seconds
        for a task to be available.
        
        Args:
            timeout: Seconds to wait for a task
            
        Returns:
            task_id or None if timeout
        """
        result = await self.redis.brpop(self.queue_name, timeout=timeout)
        
        if result:
            # BRPOP returns (queue_name, value)
            _, task_id = result
            task_id = task_id.decode('utf-8')
            print(f"[queue] 📤 Popped task {task_id}")
            return task_id
        
        return None
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieve task by ID
        
        Returns:
            Task object or None if not found
        """
        task_key = f"task:{task_id}"
        data = await self.redis.hgetall(task_key)
        
        if not data:
            return None
        
        return redis_to_task(data)

    async def set_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        result: Optional[any] = None,
        error: Optional[str] = None
    ):
        """
        Update task status and optionally result/error
        
        This is a partial update - only modifies specified fields
        """
        task_key = f"task:{task_id}"
        
        updates = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if result is not None:
            updates["result"] = json.dumps(result)
        
        if error is not None:
            updates["error"] = error
        
        await self.redis.hset(task_key, mapping=updates)
        print(f"[queue] 🔄 Task {task_id} status → {status.value}")
        
    async def publish_event(self, task_id: str, event_type: str, data: dict = None):
        """
        Publish event to task's channel
        
        WebSocket clients subscribe to this channel for real-time updates
        """
        channel = f"task:{task_id}:events"
        message = create_event(event_type, data)
        
        await self.redis.publish(channel, message)
        print(f"[queue] 📢 Published '{event_type}' event for task {task_id}")
    
    async def subscribe_task_events(self, task_id: str):
        """
        Subscribe to task events
        
        Returns:
            PubSub object - iterate over it to receive messages
        """
        channel = f"task:{task_id}:events"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        
        print(f"[queue] 👂 Subscribed to events for task {task_id}")
        return pubsub
    
    async def get_queue_length(self) -> int:
        """Get number of tasks waiting in queue"""
        return await self.redis.llen(self.queue_name)
    
    async def delete_task(self, task_id: str):
        """Delete task metadata (cleanup)"""
        task_key = f"task:{task_id}"
        await self.redis.delete(task_key)
        print(f"[queue] 🗑️  Deleted task {task_id}")
    
    async def task_exists(self, task_id: str) -> bool:
        """Check if task exists"""
        task_key = f"task:{task_id}"
        return await self.redis.exists(task_key) > 0
    
    async def requeue_task(self, task_id: str):
        """
        Requeue a failed task for retry
        
        Increments retry_count and resets status to PENDING
        """
        task = await self.get_task(task_id)
        
        if not task:
            print(f"[queue] ⚠️  Cannot requeue - task {task_id} not found")
            return False
        
        # Increment retry count
        task.retry_count += 1
        
        updates = {
            "status": TaskStatus.RETRY.value,
            "retry_count": str(task.retry_count),
            "updated_at": datetime.utcnow().isoformat(),
            "processing_started_at": ""  # Reset processing time
        }
        
        task_key = f"task:{task_id}"
        await self.redis.hset(task_key, mapping=updates)
        
        # Add back to queue
        await self.redis.lpush(self.queue_name, task_id)
        
        print(f"[queue] 🔄 Requeued task {task_id} (retry {task.retry_count}/{task.max_retries})")
        return True
    
    async def move_to_dead_letter(self, task_id: str):
        """
        Move task to dead-letter queue after max retries exceeded
        """
        dead_letter_queue = "queue:dead_letter"
        
        # Add to dead-letter queue
        await self.redis.lpush(dead_letter_queue, task_id)
        
        # Update task status
        updates = {
            "status": TaskStatus.FAILED.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        task_key = f"task:{task_id}"
        await self.redis.hset(task_key, mapping=updates)
        
        print(f"[queue] 💀 Moved task {task_id} to dead-letter queue")
    
    async def get_dead_letter_tasks(self) -> list[str]:
        """Get all task IDs in dead-letter queue"""
        dead_letter_queue = "queue:dead_letter"
        tasks = await self.redis.lrange(dead_letter_queue, 0, -1)
        return [t.decode('utf-8') for t in tasks]
    
    async def set_processing_started(self, task_id: str):
        """
        Mark when task processing started (for visibility timeout)
        """
        updates = {
            "processing_started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        task_key = f"task:{task_id}"
        await self.redis.hset(task_key, mapping=updates)

# Global instance
queue = RedisQueue()