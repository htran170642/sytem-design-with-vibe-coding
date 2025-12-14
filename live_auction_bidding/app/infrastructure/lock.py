# redis_lock.py
"""
Simple and effective distributed lock with retry tracking
"""
import time
import uuid
import redis
from contextlib import contextmanager

class AuctionLock:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.lock_expire_ms = 3000
        self.retry_delay = 0.005  # ← Change from 0.02 to 0.005 (5ms)
        self.max_retries = 10 
        
        # Lua script for atomic unlock
        self.unlock_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
    
    def acquire(self, auction_id: int) -> tuple[str, str, int]:
        """
        Try to acquire lock with retry
        
        Returns: (lock_key, request_id, retry_count)
        Raises: TimeoutError if can't acquire
        """
        lock_key = f"auction:lock:{auction_id}"
        request_id = str(uuid.uuid4())
        
        for attempt in range(self.max_retries):
            acquired = self.redis.set(
                lock_key,
                request_id,
                nx=True,
                px=self.lock_expire_ms
            )
            
            if acquired:
                return lock_key, request_id, attempt  # Return retry count
            
            # Backoff before retry
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        # Failed to acquire after all retries
        raise TimeoutError(f"Could not acquire lock for auction {auction_id}")
    
    def release(self, lock_key: str, request_id: str):
        """Release lock only if we own it"""
        try:
            self.redis.eval(self.unlock_script, 1, lock_key, request_id)
        except Exception as e:
            print(f"⚠️  Error releasing lock: {e}")
    
    @contextmanager
    def lock(self, auction_id: int):
        """
        Context manager for easy usage
        
        Usage:
            with lock_manager.lock(auction_id) as retry_count:
                print(f"Acquired after {retry_count} retries")
                process_bid()
        """
        lock_key, request_id, retry_count = self.acquire(auction_id)
        
        try:
            yield retry_count
        finally:
            self.release(lock_key, request_id)