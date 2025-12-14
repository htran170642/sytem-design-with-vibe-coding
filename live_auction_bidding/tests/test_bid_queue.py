"""
Test the bid queue
"""
from redis_client import get_redis_client
from bid_queue import BidQueue

def test_basic_queue():
    """Test basic queue operations"""
    
    redis = get_redis_client()
    queue = BidQueue(redis)
    
    print("📝 Test 1: Enqueue bids")
    
    # Add 3 bids
    bid_id1 = queue.enqueue_bid(123, 1, 100.00)
    bid_id2 = queue.enqueue_bid(123, 2, 110.00)
    bid_id3 = queue.enqueue_bid(123, 3, 120.00)
    
    print(f"   Added: {bid_id1}, {bid_id2}, {bid_id3}")
    
    # Check queue length
    length = queue.get_queue_length(123)
    print(f"   Queue length: {length}")
    assert length == 3, "Should have 3 bids"
    
    print("\n📝 Test 2: Dequeue bids (FIFO)")
    
    # Dequeue in order
    bid1 = queue.dequeue_bid(123)
    print(f"   Dequeued: User {bid1['user_id']}, ${bid1['bid_amount']}")
    assert bid1['user_id'] == 1, "First bid should be user 1"
    
    bid2 = queue.dequeue_bid(123)
    print(f"   Dequeued: User {bid2['user_id']}, ${bid2['bid_amount']}")
    assert bid2['user_id'] == 2, "Second bid should be user 2"
    
    bid3 = queue.dequeue_bid(123)
    print(f"   Dequeued: User {bid3['user_id']}, ${bid3['bid_amount']}")
    assert bid3['user_id'] == 3, "Third bid should be user 3"
    
    # Queue should be empty now
    length = queue.get_queue_length(123)
    print(f"   Queue length: {length}")
    assert length == 0, "Queue should be empty"
    
    print("\n📝 Test 3: Check bid status")
    
    # Check status
    status = queue.get_bid_status(bid_id1)
    print(f"   Bid {bid_id1[:8]}... status: {status['status']}")
    assert status['status'] == 'QUEUED', "Status should be QUEUED"
    
    # Update status
    queue.update_bid_status(bid_id1, "SUCCESS", {"result": "won"})
    
    status = queue.get_bid_status(bid_id1)
    print(f"   Updated status: {status['status']}")
    assert status['status'] == 'SUCCESS', "Status should be SUCCESS"
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_basic_queue()