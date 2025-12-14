"""
Background Worker Process

Processes bids from Redis queue with:
- Distributed locking
- Cache invalidation
- Pub/Sub broadcasting
"""
import asyncio
import sys
import signal
from sqlalchemy.orm import Session
from datetime import datetime

# Updated imports for new structure
from app.infrastructure.database import SessionLocal
from app.models import Auction, Bid
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.lock import AuctionLock
from app.infrastructure.queue import BidQueue
from app.infrastructure.cache import AuctionCache
from app.infrastructure.pubsub import get_pubsub_manager


class BidWorker:
    """
    Background worker that processes bids from queue
    
    Responsibilities:
    1. Monitor queue for new bids
    2. Acquire lock before processing
    3. Validate and process bid
    4. Update database
    5. Invalidate cache
    6. Broadcast WebSocket update via Pub/Sub
    7. Update bid status
    """
    
    def __init__(self, worker_id: int):
        """
        Initialize worker
        
        Args:
            worker_id: Unique worker identifier (1, 2, 3, ...)
        """
        self.worker_id = worker_id
        self.redis = get_redis_client()
        self.queue = BidQueue(self.redis)
        self.lock_manager = AuctionLock(self.redis)
        self.cache = AuctionCache(self.redis)
        self.pubsub = None  # Will initialize in async context
        
        self.processed_count = 0
        self.running = True
        
        # Statistics
        self.success_count = 0
        self.rejected_count = 0
        self.error_count = 0
    
    async def initialize_pubsub(self):
        """Initialize Pub/Sub connection"""
        self.pubsub = get_pubsub_manager()
        await self.pubsub.connect()
    
    def process_bid(self, bid_data: dict, db: Session) -> dict:
        """
        Process a single bid with full validation
        
        Args:
            bid_data: Bid information from queue
            db: Database session
            
        Returns:
            Result dict with bid and auction data
            
        Raises:
            Exception: If validation fails
        """
        auction_id = bid_data['auction_id']
        user_id = bid_data['user_id']
        bid_amount = bid_data['bid_amount']
        
        print(f"🔍 [Worker {self.worker_id}] Processing bid: "
              f"User {user_id} → ${bid_amount} on auction {auction_id}")
        
        # Get auction from database (FRESH data, not cache!)
        auction = db.query(Auction).filter(
            Auction.auction_id == auction_id
        ).first()
        
        if not auction:
            raise Exception("Auction not found")
        
        # Validate auction status
        if auction.status != "ACTIVE":
            raise Exception(f"Auction is {auction.status}")
        
        # Check if auction ended
        if datetime.now() > auction.end_time:
            auction.status = "ENDED"
            db.commit()
            raise Exception("Auction has ended")
        
        # Check if user is already winning
        if auction.current_winner_id == user_id:
            raise Exception("You are already the highest bidder")
        
        # Validate bid amount
        required_bid = auction.current_price + auction.min_increment
        if bid_amount < required_bid:
            raise Exception(f"Bid must be at least ${required_bid:.2f}")
        
        # All validation passed - update auction
        old_price = auction.current_price
        old_winner = auction.current_winner_id
        
        auction.current_price = bid_amount
        auction.current_winner_id = user_id
        auction.total_bids += 1
        
        # Create bid record
        bid = Bid(
            auction_id=auction_id,
            user_id=user_id,
            bid_amount=bid_amount,
            previous_price=old_price
        )
        
        db.add(bid)
        db.commit()
        db.refresh(bid)
        db.refresh(auction)
        
        print(f"✅ [Worker {self.worker_id}] DB updated: "
              f"${old_price} → ${bid_amount}")
        
        return {
            "success": True,
            "message": "Bid placed successfully",
            "bid": bid.to_dict(),
            "auction": auction.to_dict(),
            "old_winner": old_winner
        }
    
    async def process_auction_queue(self, auction_id: int):
        """
        Process all pending bids for a specific auction
        
        Args:
            auction_id: Which auction to process
        """
        print(f"📋 [Worker {self.worker_id}] Processing auction {auction_id} queue")
        
        db = SessionLocal()
        
        try:
            while self.running:
                # Get next bid from queue (blocking, timeout 1s)
                bid_data = self.queue.dequeue_bid(auction_id, timeout=1)
                
                if not bid_data:
                    break  # No more bids
                
                bid_id = bid_data['bid_id']
                
                try:
                    # Acquire lock for this auction
                    with self.lock_manager.lock(auction_id) as retry_count:
                        
                        if retry_count > 0:
                            print(f"🔒 [Worker {self.worker_id}] Lock acquired "
                                  f"after {retry_count} retries")
                        
                        # Process the bid
                        result = self.process_bid(bid_data, db)
                        
                        # Invalidate cache (data changed!)
                        self.cache.invalidate_auction_with_bids(auction_id, db)
                        print(f"🗑️  [Worker {self.worker_id}] Cache invalidated for auction {auction_id}")
                        
                        # Update bid status to SUCCESS
                        self.queue.update_bid_status(bid_id, "SUCCESS", result)
                        
                        # Get recent bids for broadcast
                        recent_bids = db.query(Bid).filter(
                            Bid.auction_id == auction_id
                        ).order_by(Bid.bid_time.desc()).limit(5).all()
                        
                        # Publish to Redis Pub/Sub (broadcasts to all servers)
                        await self.pubsub.publish_to_auction(auction_id, {
                            "type": "NEW_BID",
                            "auction_id": auction_id,
                            "bid": result["bid"],
                            "auction": result["auction"],
                            "old_winner": result["old_winner"],
                            "recent_bids": [bid.to_dict() for bid in recent_bids]
                        })
                        
                        # Statistics
                        self.processed_count += 1
                        self.success_count += 1
                        
                        print(f"💰 [Worker {self.worker_id}] SUCCESS: "
                              f"Bid {bid_id[:8]}... processed "
                              f"(total: {self.processed_count})")
                
                except Exception as e:
                    # Bid failed validation
                    error_message = str(e)
                    
                    self.queue.update_bid_status(bid_id, "REJECTED", {
                        "error": error_message
                    })
                    
                    self.rejected_count += 1
                    
                    print(f"❌ [Worker {self.worker_id}] REJECTED: "
                          f"Bid {bid_id[:8]}... - {error_message}")
        
        except Exception as e:
            print(f"❌ [Worker {self.worker_id}] ERROR in process_auction_queue: {e}")
            import traceback
            traceback.print_exc()
            self.error_count += 1
        
        finally:
            db.close()
    
    async def run(self):
        """
        Main worker loop
        
        Continuously monitors all active auctions and processes their queues
        """
        print(f"🚀 [Worker {self.worker_id}] Started")
        print(f"   Cache enabled: ✅")
        print(f"   Pub/Sub: Initializing...")
        
        # Initialize Pub/Sub
        await self.initialize_pubsub()
        print(f"   Pub/Sub: ✅")
        
        db = SessionLocal()
        
        try:
            while self.running:
                # Get all active auctions
                active_auctions = db.query(Auction).filter(
                    Auction.status == "ACTIVE"
                ).all()
                
                if not active_auctions:
                    # No active auctions, wait a bit
                    await asyncio.sleep(1)
                    continue
                
                # Check each auction's queue
                for auction in active_auctions:
                    queue_length = self.queue.get_queue_length(auction.auction_id)
                    
                    if queue_length > 0:
                        print(f"📊 [Worker {self.worker_id}] "
                              f"Auction {auction.auction_id} has {queue_length} pending bids")
                        
                        # Process this auction's queue
                        await self.process_auction_queue(auction.auction_id)
                
                # Small delay before checking again
                await asyncio.sleep(0.1)
        
        finally:
            db.close()
            
            # Print final statistics
            print(f"\n🛑 [Worker {self.worker_id}] Stopped")
            print(f"   Total processed: {self.processed_count}")
            print(f"   Successful: {self.success_count}")
            print(f"   Rejected: {self.rejected_count}")
            print(f"   Errors: {self.error_count}")
            
            # Print cache statistics
            cache_stats = self.cache.get_stats()
            print(f"   Cache hit rate: {cache_stats['hit_rate']:.1%}")


async def main():
    """
    Main entry point for worker process
    
    Usage:
        python -m worker.bid_worker 1   # Start worker 1
        python -m worker.bid_worker 2   # Start worker 2
        python -m worker.bid_worker 3   # Start worker 3
    """
    # Get worker ID from command line argument
    worker_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    worker = BidWorker(worker_id)
    
    # Handle graceful shutdown (Ctrl+C)
    def signal_handler(sig, frame):
        print(f"\n⚠️  [Worker {worker_id}] Shutdown signal received...")
        worker.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        print(f"\n⚠️  [Worker {worker_id}] Keyboard interrupt")
        worker.running = False

if __name__ == "__main__":
    print("=" * 70)
    print("🎯 Background Bid Worker")
    print("=" * 70)
    
    asyncio.run(main())