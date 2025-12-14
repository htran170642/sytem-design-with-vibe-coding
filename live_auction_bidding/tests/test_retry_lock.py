# test_retry_lock.py

import requests
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8000"


def place_bid_request(auction_id, user_id, bid_amount):
    """Place bid and capture retry information"""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{BASE_URL}/auctions/{auction_id}/bids",
            json={"user_id": user_id, "bid_amount": bid_amount}
        )
        
        end_time = time.time()
        
        result = {
            "user_id": user_id,
            "bid_amount": bid_amount,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "start_time": start_time,
            "end_time": end_time,
            "duration": end_time - start_time,
            "retry_count": 0
        }
        
        if response.status_code == 200:
            # Extract retry count from response
            response_data = response.json()
            result["retry_count"] = response_data.get("retry_count", 0)
        else:
            try:
                result["error"] = response.json().get("detail", "Unknown error")
            except:
                result["error"] = response.text
        
        return result
        
    except Exception as e:
        return {
            "user_id": user_id,
            "bid_amount": bid_amount,
            "success": False,
            "error": str(e),
            "retry_count": 0
        }


def test_retry_behavior():
    print("\n" + "="*70)
    print("TEST: Retry-Based Lock with Retry Tracking")
    print("="*70)
    
    # Create auction
    response = requests.post(f"{BASE_URL}/auctions", json={
        "title": "Retry Tracking Test",
        "description": "Testing retry behavior with tracking",
        "starting_price": 100,
        "min_increment": 10,
        "duration_minutes": 60
    })
    auction_id = response.json()["auction"]["auction_id"]
    print(f"✅ Created auction {auction_id}\n")
    
    print("🏃 Launching 20 users bidding simultaneously...\n")
    
    # Launch 20 concurrent bids
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        
        for user_id in range(1, 21):
            bid_amount = 110 + (user_id * 10)
            future = executor.submit(place_bid_request, auction_id, user_id, bid_amount)
            futures.append(future)
        
        results = [future.result() for future in futures]
    
    # Sort by completion time (processing order)
    results.sort(key=lambda x: x['end_time'])
    
    print("📊 Results (in ACTUAL PROCESSING ORDER):\n")
    
    for i, result in enumerate(results, 1):
        user_id = result['user_id']
        bid_amount = result['bid_amount']
        retry_count = result['retry_count']
        duration = result['duration']
        
        if result['success']:
            retry_info = f"({retry_count} retries)" if retry_count > 0 else "(no retry)"
            print(f"{i:2d}. User {user_id:2d}: ${bid_amount} - ✅ SUCCESS {retry_info} [{duration:.3f}s]")
        else:
            error = result.get('error', 'Unknown')
            print(f"{i:2d}. User {user_id:2d}: ${bid_amount} - ❌ FAIL [{duration:.3f}s]")
            if isinstance(error, dict):
                print(f"     Reason: {error.get('message', error)}")
            else:
                print(f"     Reason: {error}")
    
    # Statistics
    print("\n" + "="*70)
    print("📈 Statistics:\n")
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"Total bids: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        total_retries = sum(r['retry_count'] for r in successful)
        avg_retries = total_retries / len(successful)
        max_retries = max(r['retry_count'] for r in successful)
        
        print(f"\nRetry Statistics:")
        print(f"  Total retries: {total_retries}")
        print(f"  Average retries per bid: {avg_retries:.2f}")
        print(f"  Max retries by a single bid: {max_retries}")
        
        # Show which users had most retries
        sorted_by_retries = sorted(successful, key=lambda x: x['retry_count'], reverse=True)
        print(f"\n  Top 3 users with most retries:")
        for r in sorted_by_retries[:3]:
            print(f"    User {r['user_id']}: {r['retry_count']} retries")
    
    # Also show sorted by user_id
    print("\n" + "="*70)
    print("📊 Same Results (sorted by USER ID):\n")
    
    results.sort(key=lambda x: x['user_id'])
    
    for result in results:
        user_id = result['user_id']
        bid_amount = result['bid_amount']
        retry_count = result['retry_count']
        
        if result['success']:
            retry_info = f"({retry_count} retries)" if retry_count > 0 else "(no retry)"
            print(f"✅ User {user_id:2d}: ${bid_amount} - SUCCESS {retry_info}")
        else:
            error = result.get('error', 'Unknown')
            print(f"❌ User {user_id:2d}: ${bid_amount} - FAIL")
            if isinstance(error, dict):
                print(f"   Reason: {error.get('message', error)}")
            else:
                print(f"   Reason: {error}")
    
    # Final state
    response = requests.get(f"{BASE_URL}/auctions/{auction_id}")
    auction = response.json()["auction"]
    
    print(f"\n🏆 Final State:")
    print(f"   Winner: User {auction['current_winner_id']}")
    print(f"   Price: ${auction['current_price']}")
    print(f"   Total Bids: {auction['total_bids']}")


if __name__ == "__main__":
    test_retry_behavior()