"""
Idempotency key system to prevent duplicate bookings
Handles retries and network failures gracefully
"""
from typing import Optional, Any
import hashlib
import json
import time
from app.core.redis import redis_client
import logging

logger = logging.getLogger(__name__)


class IdempotencyService:
    """
    Manages idempotency keys for booking operations
    
    Prevents duplicate bookings when users:
    - Click button multiple times
    - Retry due to network timeout
    - Browser refresh during processing
    """
    
    def __init__(self):
        self.redis = redis_client
        self.ttl = 86400  # 24 hours
    
    def generate_key(self, user_id: int, operation: str, params: dict) -> str:
        """
        Generate idempotency key from operation parameters
        
        Args:
            user_id: User performing the operation
            operation: Type of operation (e.g., 'create_booking')
            params: Operation parameters
        
        Returns:
            SHA256 hash of the combined parameters
        """
        # Create consistent representation
        key_data = {
            "user_id": user_id,
            "operation": operation,
            "params": sorted(params.items())  # Sort for consistency
        }
        
        # Generate hash
        key_string = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.sha256(key_string.encode()).hexdigest()
        
        return f"idempotency:{operation}:{hash_key}"
    
    async def check_operation(self, idempotency_key: str) -> Optional[dict]:
        """
        Check if operation was already performed
        
        Returns:
            - None if operation is new
            - Previous result if operation was already completed
        """
        result = await self.redis.get(idempotency_key)
        
        if result:
            logger.info(f"♻️ Idempotent operation detected: {idempotency_key}")
        
        return result
    
    async def store_result(self, idempotency_key: str, result: Any):
        """
        Store operation result for future idempotent requests
        
        Args:
            idempotency_key: The idempotency key
            result: Operation result to cache
        """
        await self.redis.set(idempotency_key, result, ttl=self.ttl)
        logger.info(f"💾 Stored idempotent result: {idempotency_key}")
    
    async def lock_operation(self, idempotency_key: str, ttl: int = 30) -> bool:
        """
        Acquire lock for operation in progress
        Prevents concurrent execution of same operation
        
        Returns:
            True if lock acquired, False if already locked
        """
        lock_key = f"{idempotency_key}:lock"
        
        # Try to set lock (NX = only if not exists)
        acquired = await self.redis.redis.set(
            lock_key,
            time.time(),
            ex=ttl,
            nx=True
        )
        
        return bool(acquired)
    
    async def release_lock(self, idempotency_key: str):
        """Release operation lock"""
        lock_key = f"{idempotency_key}:lock"
        await self.redis.delete(lock_key)


# Global instance
idempotency_service = IdempotencyService()
