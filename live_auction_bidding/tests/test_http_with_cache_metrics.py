"""
HTTP Test with Proper Cache Metrics Tracking
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
import time
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8000"


def test_http_with_cache_comparison():
    """
    Compare HTTP requests with and without cache
    """
    print("\n" + "=" * 70)
    print("HTTP Performance Test - Cache Comparison")
    print("=" * 70)
    
    num_requests = 10000
    num_workers = 200
    
    # Get a test auction
    response = requests.get(f"{BASE_URL}/auctions?limit=1")
    auctions = response.json()['auctions']
    if not auctions:
        print("❌ No auctions found!")
        return
    
    test_auction_id = auctions[0]['auction_id']
    
    print(f"\n📊 Configuration:")
    print(f"   Requests: {num_requests:,}")
    print(f"   Workers: {num_workers}")
    print(f"   Test Auction: {test_auction_id}")
    
    # ────────────────────────────────────────────────────────────
    # TEST 1: WITHOUT CACHE (clear first)
    # ────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("TEST 1: WITHOUT CACHE")
    print("─" * 70)
    
    # Clear cache
    requests.delete(f"{BASE_URL}/admin/cache/clear")
    print("🗑️  Cache cleared")
    
    # Get initial stats
    initial_stats = requests.get(f"{BASE_URL}/admin/cache-stats").json()
    print(f"Initial cache hits: {initial_stats.get('auctions', {}).get('hits', 0)}")
    
    times_no_cache = []
    
    def make_request_no_cache(i):
        # Clear cache before each request to simulate no cache
        if i % 10 == 0:
            requests.delete(f"{BASE_URL}/admin/cache/clear")
        
        start = time.perf_counter()
        response = requests.get(f"{BASE_URL}/auctions/{test_auction_id}")
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, response.status_code == 200
    
    print(f"🚀 Running {num_requests:,} requests WITHOUT cache...")
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(make_request_no_cache, i) for i in range(num_requests)]
        
        for future in as_completed(futures):
            elapsed, success = future.result()
            if success:
                times_no_cache.append(elapsed)
    
    total_time_no_cache = (time.perf_counter() - start_time) * 1000
    
    # Results
    print(f"\n📊 Results WITHOUT Cache:")
    print(f"   Total Time: {total_time_no_cache:,.2f} ms ({total_time_no_cache/1000:.2f}s)")
    print(f"   Mean: {statistics.mean(times_no_cache):.2f} ms")
    print(f"   Median: {statistics.median(times_no_cache):.2f} ms")
    print(f"   Throughput: {num_requests / (total_time_no_cache/1000):,.2f} req/s")
    
    # ────────────────────────────────────────────────────────────
    # TEST 2: WITH CACHE (warmed)
    # ────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("TEST 2: WITH CACHE")
    print("─" * 70)
    
    # Warm cache
    requests.post(f"{BASE_URL}/admin/cache/warm")
    print("🔥 Cache warmed")
    
    # Verify cache is working
    for _ in range(10):
        requests.get(f"{BASE_URL}/auctions/{test_auction_id}")
    
    warm_stats = requests.get(f"{BASE_URL}/admin/cache-stats").json()
    print(f"Cache hits after warming: {warm_stats.get('auctions', {}).get('hits', 0)}")
    
    times_with_cache = []
    
    def make_request_with_cache(i):
        start = time.perf_counter()
        response = requests.get(f"{BASE_URL}/auctions/{test_auction_id}")
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, response.status_code == 200
    
    print(f"🚀 Running {num_requests:,} requests WITH cache...")
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(make_request_with_cache, i) for i in range(num_requests)]
        
        for future in as_completed(futures):
            elapsed, success = future.result()
            if success:
                times_with_cache.append(elapsed)
    
    total_time_with_cache = (time.perf_counter() - start_time) * 1000
    
    # Get final cache stats
    final_stats = requests.get(f"{BASE_URL}/admin/cache-stats").json()
    
    # Results
    print(f"\n📊 Results WITH Cache:")
    print(f"   Total Time: {total_time_with_cache:,.2f} ms ({total_time_with_cache/1000:.2f}s)")
    print(f"   Mean: {statistics.mean(times_with_cache):.2f} ms")
    print(f"   Median: {statistics.median(times_with_cache):.2f} ms")
    print(f"   Throughput: {num_requests / (total_time_with_cache/1000):,.2f} req/s")
    print(f"   Cache Hits: {final_stats.get('auctions', {}).get('hits', 0):,}")
    print(f"   Cache Hit Rate: {final_stats.get('auctions', {}).get('hit_rate', 0):.1%}")
    
    # ────────────────────────────────────────────────────────────
    # COMPARISON
    # ────────────────────────────────────────────────────────────
    speedup = total_time_no_cache / total_time_with_cache
    mean_speedup = statistics.mean(times_no_cache) / statistics.mean(times_with_cache)
    throughput_increase = (num_requests / (total_time_with_cache/1000)) / (num_requests / (total_time_no_cache/1000))
    
    print("\n" + "=" * 70)
    print("🏆 COMPARISON")
    print("=" * 70)
    print(f"\nTotal Time:")
    print(f"   Without Cache: {total_time_no_cache:,.2f} ms")
    print(f"   With Cache:    {total_time_with_cache:,.2f} ms")
    print(f"   ⚡ Speedup:     {speedup:.1f}x faster!")
    
    print(f"\nMean Response:")
    print(f"   Without Cache: {statistics.mean(times_no_cache):.2f} ms")
    print(f"   With Cache:    {statistics.mean(times_with_cache):.2f} ms")
    print(f"   ⚡ Speedup:     {mean_speedup:.1f}x faster!")
    
    print(f"\nThroughput:")
    print(f"   Without Cache: {num_requests / (total_time_no_cache/1000):,.2f} req/s")
    print(f"   With Cache:    {num_requests / (total_time_with_cache/1000):,.2f} req/s")
    print(f"   ⚡ Increase:    {throughput_increase:.1f}x more requests!")
    
    print("=" * 70)


if __name__ == "__main__":
    print("🧪 HTTP Performance Test with Cache Comparison")
    print("\n⚠️  Server must be running: python run.py")
    input("\nPress Enter to start...")
    
    test_http_with_cache_comparison()