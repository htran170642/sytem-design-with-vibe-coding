"""
Bid Queue System using Redis Lists

Redis Lists are perfect for queues because:
1. LPUSH = Add to left (head) - O(1) time complexity
2. BRPOP = Pop from right (tail) with blocking - O(1) time
3. LLEN = Get length - O(1) time
4. Atomic operations (thread-safe)
"""

import json
import time
import uuid
from typing import Optional, Dict
import redis
from app.core.config import get_settings


class BidQueue:
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize queue manager
        
        Args:
            redis_client: Connected Redis client
        """
        self.redis = redis_client
        
        settings = get_settings()
        self.ttl = settings.BID_QUEUE_TTL
    
    def enqueue_bid(self, auction_id: int, user_id: int, bid_amount: float) -> str:
        """
        Add bid to queue (INSTANT operation!)
        
        This is the KEY to scaling:
        - User gets immediate response
        - Bid is safely stored in Redis
        - Worker will process it later
        
        Args:
            auction_id: Which auction
            user_id: Who is bidding
            bid_amount: How much
            
        Returns:
            bid_id: Unique ID to track this bid
            
        Example:
            >>> queue = BidQueue(redis_client)
            >>> bid_id = queue.enqueue_bid(123, 456, 1500.00)
            >>> print(bid_id)
            'a3f7b2d1-4e6c-4b9a-8f2e-9d1c3e5a7b9f'
        """
        
        # Step 1: Generate unique bid ID
        # UUID4 = Random UUID (virtually impossible to collide)
        bid_id = str(uuid.uuid4())
        
        # Step 2: Create bid data structure
        bid_data = {
            "bid_id": bid_id,
            "auction_id": auction_id,
            "user_id": user_id,
            "bid_amount": bid_amount,
            "timestamp": time.time(),      # Unix timestamp (seconds since 1970)
            "status": "QUEUED"             # Initial status
        }
        
        # Step 3: Add to auction-specific queue
        # Key pattern: "bid_queue:{auction_id}"
        # Example: "bid_queue:123"
        # Why auction-specific? So we can process each auction independently
        queue_key = f"bid_queue:{auction_id}"
        
        # LPUSH = List Push (add to left/head of list)
        # Converts dict to JSON string before storing
        # Redis command: LPUSH bid_queue:123 '{"bid_id":"...", ...}'
        self.redis.lpush(queue_key, json.dumps(bid_data))
        
        # Step 4: Store bid metadata separately for status checking
        # This allows users to check "Is my bid processed yet?"
        # Key pattern: "bid_meta:{bid_id}"
        # TTL = 300 seconds (5 minutes) - auto-delete after processing
        self.redis.setex(
            f"bid_meta:{bid_id}",
            self.ttl,  # TTL in seconds
            json.dumps(bid_data)
        )
        
        # Step 5: Log for debugging
        print(f"📥 Queued bid {bid_id} for auction {auction_id}")
        
        # Return bid_id so user can track it
        return bid_id
    
    
    def dequeue_bid(self, auction_id: int, timeout: int = 1) -> Optional[Dict]:
        """
        Get next bid from queue (BLOCKING operation)
        
        This is called by WORKER processes, not by users!
        
        BRPOP = Blocking Right Pop
        - Waits up to 'timeout' seconds for a bid
        - If no bid arrives, returns None
        - If bid arrives, immediately returns it
        
        Why blocking?
        - Worker doesn't need to poll constantly
        - Saves CPU cycles
        - Immediately processes when bid arrives
        
        Args:
            auction_id: Which auction's queue to check
            timeout: How long to wait (seconds)
            
        Returns:
            Bid data dict, or None if timeout
            
        Example:
            >>> # Worker process:
            >>> while True:
            >>>     bid = queue.dequeue_bid(123, timeout=5)
            >>>     if bid:
            >>>         process_bid(bid)
        """
        
        queue_key = f"bid_queue:{auction_id}"
        
        # BRPOP = Blocking Right Pop
        # Waits up to 'timeout' seconds for an item
        # Returns: (key, value) tuple or None
        result = self.redis.brpop(queue_key, timeout=timeout)
        
        if result:
            # result[0] = queue key (e.g., "bid_queue:123")
            # result[1] = JSON string of bid data
            _, bid_json = result
            
            # Parse JSON string back to dict
            return json.loads(bid_json)
        
        # Timeout reached, no bid available
        return None
    
    
    def get_bid_status(self, bid_id: str) -> Optional[Dict]:
        """
        Check the status of a bid
        
        Users call this to see: "Is my bid processed yet?"
        
        Status values:
        - "QUEUED": Still waiting in queue
        - "PROCESSING": Worker is processing it
        - "SUCCESS": Bid was accepted
        - "REJECTED": Bid failed validation
        
        Args:
            bid_id: The unique bid ID returned from enqueue_bid()
            
        Returns:
            Bid metadata dict, or None if not found
            
        Example:
            >>> status = queue.get_bid_status(bid_id)
            >>> if status['status'] == 'SUCCESS':
            >>>     print("Your bid won!")
        """
        
        # Get metadata from Redis
        meta = self.redis.get(f"bid_meta:{bid_id}")
        
        if meta:
            return json.loads(meta)
        
        # Not found (expired or never existed)
        return None
    
    
    def update_bid_status(self, bid_id: str, status: str, result: Dict = None):
        """
        Update bid status after processing
        
        Called by WORKER after processing bid
        
        Args:
            bid_id: Which bid
            status: New status ("SUCCESS", "REJECTED", etc.)
            result: Additional data (optional)
            
        Example:
            >>> # Worker after processing:
            >>> queue.update_bid_status(
            >>>     bid_id,
            >>>     "SUCCESS",
            >>>     {"final_price": 1500.00, "winner": True}
            >>> )
        """
        
        # Get current metadata
        meta = self.get_bid_status(bid_id)
        
        if meta:
            # Update status
            meta['status'] = status
            
            # Add result data if provided
            if result:
                meta['result'] = result
            
            # Save back to Redis (refresh TTL to 5 minutes)
            self.redis.setex(
                f"bid_meta:{bid_id}",
                self.ttl,  # 5 minutes TTL
                json.dumps(meta)
            )
    
    
    def get_queue_length(self, auction_id: int) -> int:
        """
        Get number of pending bids in queue
        
        Useful for:
        - Showing users: "Your position: 42 in queue"
        - Monitoring: "Alert if queue > 1000"
        - Load balancing: "Start more workers if queue > 100"
        
        Args:
            auction_id: Which auction
            
        Returns:
            Number of bids waiting
            
        Example:
            >>> length = queue.get_queue_length(123)
            >>> print(f"There are {length} bids waiting")
        """
        
        queue_key = f"bid_queue:{auction_id}"
        
        # LLEN = List Length (O(1) operation - very fast!)
        return self.redis.llen(queue_key)