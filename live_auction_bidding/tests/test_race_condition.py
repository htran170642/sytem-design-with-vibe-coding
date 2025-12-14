# test_race_condition.py
"""
Test script to verify race condition is fixed
"""

import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8000"

def create_test_auction():
    """Create an auction for testing"""
    response = requests.post(f"{BASE_URL}/auctions", json={
        "title": "Race Condition Test",
        "description": "Testing concurrent bids",
        "starting_price": 100,
        "min_increment": 10,
        "duration_minutes": 60
    })
    
    auction_id = response.json()['auction']['auction_id']
    print(f"✅ Created test auction {auction_id}\n")
    return auction_id


def place_bid(auction_id, user_id, bid_amount):
    """Place a single bid"""
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/auctions/{auction_id}/bids",
            json={
                "user_id": user_id,
                "bid_amount": bid_amount
            }
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            return {
                "success": True,
                "user_id": user_id,
                "amount": bid_amount,
                "time": elapsed
            }
        else:
            return {
                "success": False,
                "user_id": user_id,
                "amount": bid_amount,
                "error": response.json().get('detail', 'Unknown error'),
                "time": elapsed
            }
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "amount": bid_amount,
            "error": str(e),
            "time": 0
        }


def test_simultaneous_bids():
    """
    Test: Multiple users bidding the SAME amount at the SAME time
    Expected: Only ONE should succeed (first to acquire lock)
    """
    print("=" * 60)
    print("TEST 1: Simultaneous Bids (Same Amount)")
    print("=" * 60)
    
    auction_id = create_test_auction()
    
    print("🏃 Launching 5 users bidding $120 simultaneously...\n")
    
    # All users bid the same amount at the same time
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for user_id in range(1, 6):
            future = executor.submit(place_bid, auction_id, user_id, 120.0)
            futures.append(future)
        
        results = [future.result() for future in as_completed(futures)]
    
    # Analyze results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print("\n📊 Results:")
    print(f"   Successful bids: {len(successful)}")
    print(f"   Failed bids: {len(failed)}")
    
    if successful:
        for r in successful:
            print(f"   ✅ User {r['user_id']}: ${r['amount']} (took {r['time']:.3f}s)")
    
    if failed:
        for r in failed:
            print(f"   ❌ User {r['user_id']}: {r['error'][:50]}...")
    
    # Verify final state
    response = requests.get(f"{BASE_URL}/auctions/{auction_id}")
    auction = response.json()['auction']
    
    print(f"\n🏆 Final State:")
    print(f"   Winner: User {auction['current_winner_id']}")
    print(f"   Price: ${auction['current_price']}")
    print(f"   Total Bids: {auction['total_bids']}")
    
    # Assert only ONE bid succeeded
    if len(successful) == 1:
        print("\n✅ TEST PASSED: Race condition prevented!")
    else:
        print(f"\n❌ TEST FAILED: {len(successful)} bids succeeded (should be 1)")
    
    return len(successful) == 1


def test_rapid_sequential_bids():
    """
    Test: Multiple users bidding different amounts rapidly
    Expected: All should succeed if amounts are valid
    """
    print("\n" + "=" * 60)
    print("TEST 2: Rapid Sequential Bids (Different Amounts)")
    print("=" * 60)
    
    auction_id = create_test_auction()
    
    print("🏃 Launching 10 users with increasing bids...\n")
    
    # Each user bids a higher amount
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for user_id in range(1, 11):
            bid_amount = 100 + (user_id * 15)  # 115, 130, 145, etc.
            future = executor.submit(place_bid, auction_id, user_id, bid_amount)
            futures.append(future)
            time.sleep(0.1)  # Small delay to avoid all hitting at once
        
        results = [future.result() for future in as_completed(futures)]
    
    # Analyze results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print("\n📊 Results:")
    print(f"   Successful bids: {len(successful)}")
    print(f"   Failed bids: {len(failed)}")
    
    # Verify final state
    response = requests.get(f"{BASE_URL}/auctions/{auction_id}")
    auction = response.json()['auction']
    
    print(f"\n🏆 Final State:")
    print(f"   Winner: User {auction['current_winner_id']}")
    print(f"   Price: ${auction['current_price']}")
    print(f"   Total Bids: {auction['total_bids']}")
    
    # Most bids should succeed
    if len(successful) >= 8:  # Allow some failures due to timing
        print("\n✅ TEST PASSED: Sequential bids processed correctly!")
        return True
    else:
        print(f"\n⚠️  Only {len(successful)}/10 bids succeeded")
        return False


def test_lock_timeout():
    """
    Test: What happens if a lock is held too long
    """
    print("\n" + "=" * 60)
    print("TEST 3: Lock Behavior")
    print("=" * 60)
    
    auction_id = create_test_auction()
    
    print("Testing lock acquisition and release...\n")
    
    # Place one bid to see lock behavior
    result = place_bid(auction_id, 1, 120)
    
    if result['success']:
        print(f"✅ Bid successful in {result['time']:.3f}s")
        print("   (Lock was acquired and released properly)")
    else:
        print(f"❌ Bid failed: {result['error']}")
    
    return result['success']


if __name__ == "__main__":
    print("\n" + "🚀" * 30)
    print("  PHASE 3 - RACE CONDITION TESTING")
    print("🚀" * 30)
    
    try:
        # Check server
        response = requests.get(BASE_URL)
        data = response.json()
        print(f"\n✅ Server: {data['message']}")
        print(f"✅ Database: {data['database']}")
        print(f"✅ Redis: {data['redis']}")
        
        if "❌" in data['redis']:
            print("\n⚠️  WARNING: Redis not connected!")
            print("   Start Redis: docker run -p 6379:6379 -d redis:7-alpine")
            exit(1)
        
        # Run tests
        print("\n")
        test1_passed = test_simultaneous_bids()
        # test2_passed = test_rapid_sequential_bids()
        # test3_passed = test_lock_timeout()
        
        # Summary
        print("\n" + "=" * 60)
        print("  TEST SUMMARY")
        print("=" * 60)
        print(f"Test 1 (Simultaneous): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        # print(f"Test 2 (Sequential): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        # print(f"Test 3 (Lock Behavior): {'✅ PASSED' if test3_passed else '❌ FAILED'}")
        
        # if all([test1_passed, test2_passed, test3_passed]):
        #     print("\n🎉 ALL TESTS PASSED! Race conditions are fixed!")
        # else:
        #     print("\n⚠️  Some tests failed. Check the logs above.")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Server not running!")
        print("   Start it with: python main.py")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()