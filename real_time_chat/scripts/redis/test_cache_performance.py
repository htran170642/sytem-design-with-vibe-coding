"""
Test cache performance
"""
import time
import requests
import redis

BASE_URL = "http://localhost:8000"

def clear_redis():
    """Clear Redis database"""
    r = redis.Redis(host='localhost', port=6379)
    r.flushdb()
    print("✓ Redis cleared")

def test_without_cache_v1():
    """Method 1: Clear cache between each request"""
    print("\nMethod 1: Clearing cache between each request")
    print("-" * 50)
    
    r = redis.Redis(host='localhost', port=6379)
    times = []
    
    for i in range(10):
        # Clear cache before each request
        r.flushdb()
        
        start = time.time()
        response = requests.get(f"{BASE_URL}/messages?limit=50")
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Request {i+1}: {elapsed*1000:.2f}ms")
    
    avg = sum(times) / len(times)
    print(f"\nAverage: {avg*1000:.2f}ms")
    return avg

def test_without_cache_v2():
    """Method 2: Use different parameters"""
    print("\nMethod 2: Using different parameters (different cache keys)")
    print("-" * 50)
    
    clear_redis()
    times = []
    
    for i in range(10):
        start = time.time()
        # Each request has different limit → different cache key
        response = requests.get(f"{BASE_URL}/messages?limit={50 + i}")
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Request {i+1} (limit={50+i}): {elapsed*1000:.2f}ms")
    
    avg = sum(times) / len(times)
    print(f"\nAverage: {avg*1000:.2f}ms")
    return avg

def test_without_cache_v3():
    """Method 3: Use cache bypass parameter"""
    print("\nMethod 3: Using use_cache=false parameter")
    print("-" * 50)
    
    times = []
    
    for i in range(10):
        start = time.time()
        # use_cache=false bypasses cache
        response = requests.get(f"{BASE_URL}/messages?limit=50&use_cache=false")
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Request {i+1}: {elapsed*1000:.2f}ms")
    
    avg = sum(times) / len(times)
    print(f"\nAverage: {avg*1000:.2f}ms")
    return avg

def test_with_cache():
    """Measure response time with cache"""
    print("\nWith Cache: Same request repeated")
    print("-" * 50)
    
    clear_redis()
    
    # First request to populate cache
    requests.get(f"{BASE_URL}/messages?limit=50")
    print("Cache populated with first request\n")
    
    times = []
    for i in range(10):
        start = time.time()
        response = requests.get(f"{BASE_URL}/messages?limit=50")
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Request {i+1}: {elapsed*1000:.2f}ms")
    
    avg = sum(times) / len(times)
    print(f"\nAverage: {avg*1000:.2f}ms")
    return avg

def show_cache_keys():
    """Show what's in Redis"""
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    keys = r.keys("messages:*")
    
    print("\n=== Cache Keys in Redis ===")
    if keys:
        for key in keys:
            ttl = r.ttl(key)
            print(f"  {key} (TTL: {ttl}s)")
    else:
        print("  (empty)")

if __name__ == "__main__":
    print("=" * 60)
    print("Cache Performance Test")
    print("=" * 60)
    
    # Test with cache
    time_with_cache = test_with_cache()
    show_cache_keys()
    
    # Test without cache (multiple methods)
    print("\n" + "=" * 60)
    print("Testing WITHOUT cache (3 different methods)")
    print("=" * 60)
    
    time_without_v1 = test_without_cache_v1()
    # time_without_v2 = test_without_cache_v2()  # Uncomment if you want to test this
    # time_without_v3 = test_without_cache_v3()  # Requires main.py update
    
    # Results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"With cache:        {time_with_cache*1000:.2f}ms")
    print(f"Without cache:     {time_without_v1*1000:.2f}ms")
    print(f"Speedup:           {time_without_v1/time_with_cache:.2f}x faster")
    print(f"Time saved:        {(time_without_v1-time_with_cache)*1000:.2f}ms per request")