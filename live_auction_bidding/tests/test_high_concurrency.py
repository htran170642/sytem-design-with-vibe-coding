"""
High Concurrency Performance Tests

Tests system under extreme load:
- 10,000 concurrent requests
- Stress testing
- Load testing
- Bottleneck identification
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


import time
import statistics
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import requests
from collections import defaultdict

from app.infrastructure.database import SessionLocal
from app.infrastructure.cache import get_cache_manager
from app.models import Auction


BASE_URL = "http://localhost:8000"


class HighConcurrencyTest:
    """High concurrency testing utilities"""
    
    def __init__(self):
        self.results = []
        self.errors = []
        self.lock = threading.Lock()
    
    def record_result(self, result: Dict):
        """Thread-safe result recording"""
        with self.lock:
            self.results.append(result)
    
    def record_error(self, error: str):
        """Thread-safe error recording"""
        with self.lock:
            self.errors.append(error)
    
    def get_statistics(self) -> Dict:
        """Calculate statistics from results"""
        if not self.results:
            return {}
        
        response_times = [r['response_time'] for r in self.results]
        success_count = sum(1 for r in self.results if r['success'])
        
        # Calculate percentiles
        sorted_times = sorted(response_times)
        n = len(sorted_times)
        
        return {
            "total_requests": len(self.results),
            "successful": success_count,
            "failed": len(self.results) - success_count,
            "errors": len(self.errors),
            "min_time": min(response_times),
            "max_time": max(response_times),
            "mean_time": statistics.mean(response_times),
            "median_time": statistics.median(response_times),
            "p95_time": sorted_times[int(n * 0.95)] if n > 0 else 0,
            "p99_time": sorted_times[int(n * 0.99)] if n > 0 else 0,
            "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0
        }
    
    def reset(self):
        """Reset results"""
        self.results = []
        self.errors = []


# ============================================================================
# TEST 1: 10K CONCURRENT READS - DATABASE ONLY (NO CACHE)
# ============================================================================
def test_10k_concurrent_db_only():
    """
    Test 10,000 concurrent requests WITHOUT cache
    
    This will stress the database and show bottlenecks.
    """
    print("\n" + "=" * 70)
    print("TEST 1: 10,000 Concurrent Requests - DATABASE ONLY (NO CACHE)")
    print("=" * 70)
    print("\n⚠️  WARNING: This may take a while and stress your database!")
    print("This simulates what happens WITHOUT caching.\n")
    
    input("Press Enter to continue...")
    
    num_requests = 10000
    num_workers = 200  # Thread pool size
    
    tester = HighConcurrencyTest()
    
    # Setup: Create test auction
    db = SessionLocal()
    auction = db.query(Auction).filter(Auction.status == "ACTIVE").first()
    if not auction:
        print("❌ No active auction found. Run setup first.")
        return
    
    test_auction_id = auction.auction_id
    db.close()
    
    print(f"📊 Configuration:")
    print(f"   Total Requests: {num_requests:,}")
    print(f"   Thread Pool Size: {num_workers}")
    print(f"   Test Auction ID: {test_auction_id}")
    
    def make_db_request(request_id: int):
        """Make direct database request (no cache)"""
        db = SessionLocal()
        try:
            start = time.perf_counter()
            
            # Direct database query
            auction = db.query(Auction).filter(
                Auction.auction_id == test_auction_id
            ).first()
            
            elapsed = (time.perf_counter() - start) * 1000
            
            tester.record_result({
                "request_id": request_id,
                "response_time": elapsed,
                "success": auction is not None
            })
            
        except Exception as e:
            tester.record_error(str(e))
            tester.record_result({
                "request_id": request_id,
                "response_time": 0,
                "success": False
            })
        finally:
            db.close()
    
    # Run test
    print(f"\n🚀 Starting {num_requests:,} concurrent database requests...")
    print("Progress: ", end="", flush=True)
    
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        
        for i in range(num_requests):
            future = executor.submit(make_db_request, i)
            futures.append(future)
            
            # Show progress
            if (i + 1) % 1000 == 0:
                print(f"{i+1:,}...", end="", flush=True)
        
        # Wait for completion
        for future in as_completed(futures):
            pass
    
    total_time = (time.perf_counter() - start_time) * 1000
    
    print(" Done!")
    
    # Calculate statistics
    stats = tester.get_statistics()
    
    # Display results
    print("\n" + "─" * 70)
    print("📊 RESULTS - DATABASE ONLY (NO CACHE):")
    print("─" * 70)
    print(f"Total Time:          {total_time:,.2f} ms ({total_time/1000:.2f} seconds)")
    print(f"Total Requests:      {stats['total_requests']:,}")
    print(f"Successful:          {stats['successful']:,}")
    print(f"Failed:              {stats['failed']:,}")
    print(f"Errors:              {stats['errors']:,}")
    print(f"\nResponse Times:")
    print(f"  Min:               {stats['min_time']:.2f} ms")
    print(f"  Max:               {stats['max_time']:.2f} ms")
    print(f"  Mean:              {stats['mean_time']:.2f} ms")
    print(f"  Median:            {stats['median_time']:.2f} ms")
    print(f"  95th Percentile:   {stats['p95_time']:.2f} ms")
    print(f"  99th Percentile:   {stats['p99_time']:.2f} ms")
    print(f"  Std Deviation:     {stats['stdev']:.2f} ms")
    print(f"\nThroughput:")
    print(f"  Requests/Second:   {(num_requests / (total_time/1000)):,.2f}")
    print("─" * 70)
    
    return {
        "total_time": total_time,
        "stats": stats,
        "throughput": num_requests / (total_time/1000)
    }


# ============================================================================
# TEST 2: 10K CONCURRENT READS - WITH CACHE
# ============================================================================
def test_10k_concurrent_with_cache():
    """
    Test 10,000 concurrent requests WITH cache
    
    This should be MUCH faster and show cache effectiveness.
    """
    print("\n" + "=" * 70)
    print("TEST 2: 10,000 Concurrent Requests - WITH CACHE")
    print("=" * 70)
    
    num_requests = 10000
    num_workers = 200
    
    tester = HighConcurrencyTest()
    cache = get_cache_manager()
    
    # Setup: Create and warm cache
    db = SessionLocal()
    auction = db.query(Auction).filter(Auction.status == "ACTIVE").first()
    if not auction:
        print("❌ No active auction found. Run setup first.")
        return
    
    test_auction_id = auction.auction_id
    
    # Warm cache
    print(f"\n🔥 Warming cache for auction {test_auction_id}...")
    cache.get_auction(test_auction_id, db)
    db.close()
    
    print(f"📊 Configuration:")
    print(f"   Total Requests: {num_requests:,}")
    print(f"   Thread Pool Size: {num_workers}")
    print(f"   Test Auction ID: {test_auction_id}")
    print(f"   Cache: WARMED ✅")
    
    def make_cached_request(request_id: int):
        """Make request using cache"""
        db = SessionLocal()
        try:
            start = time.perf_counter()
            
            # Get from cache
            auction_data = cache.get_auction(test_auction_id, db)
            
            elapsed = (time.perf_counter() - start) * 1000
            
            tester.record_result({
                "request_id": request_id,
                "response_time": elapsed,
                "success": auction_data is not None
            })
            
        except Exception as e:
            tester.record_error(str(e))
            tester.record_result({
                "request_id": request_id,
                "response_time": 0,
                "success": False
            })
        finally:
            db.close()
    
    # Run test
    print(f"\n🚀 Starting {num_requests:,} concurrent cached requests...")
    print("Progress: ", end="", flush=True)
    
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        
        for i in range(num_requests):
            future = executor.submit(make_cached_request, i)
            futures.append(future)
            
            # Show progress
            if (i + 1) % 1000 == 0:
                print(f"{i+1:,}...", end="", flush=True)
        
        # Wait for completion
        for future in as_completed(futures):
            pass
    
    total_time = (time.perf_counter() - start_time) * 1000
    
    print(" Done!")
    
    # Calculate statistics
    stats = tester.get_statistics()
    
    # Get cache stats
    cache_stats = cache.get_stats()
    
    # Display results
    print("\n" + "─" * 70)
    print("📊 RESULTS - WITH CACHE:")
    print("─" * 70)
    print(f"Total Time:          {total_time:,.2f} ms ({total_time/1000:.2f} seconds)")
    print(f"Total Requests:      {stats['total_requests']:,}")
    print(f"Successful:          {stats['successful']:,}")
    print(f"Failed:              {stats['failed']:,}")
    print(f"Errors:              {stats['errors']:,}")
    print(f"\nResponse Times:")
    print(f"  Min:               {stats['min_time']:.2f} ms")
    print(f"  Max:               {stats['max_time']:.2f} ms")
    print(f"  Mean:              {stats['mean_time']:.2f} ms")
    print(f"  Median:            {stats['median_time']:.2f} ms")
    print(f"  95th Percentile:   {stats['p95_time']:.2f} ms")
    print(f"  99th Percentile:   {stats['p99_time']:.2f} ms")
    print(f"  Std Deviation:     {stats['stdev']:.2f} ms")
    print(f"\nThroughput:")
    print(f"  Requests/Second:   {(num_requests / (total_time/1000)):,.2f}")
    print(f"\nCache Performance:")
    print(f"  Hit Rate:          {cache_stats['overall_hit_rate']:.1%}")
    print("─" * 70)
    
    return {
        "total_time": total_time,
        "stats": stats,
        "cache_stats": cache_stats,
        "throughput": num_requests / (total_time/1000)
    }


# ============================================================================
# TEST 3: 10K CONCURRENT HTTP REQUESTS (API LEVEL)
# ============================================================================
def test_10k_concurrent_http_requests():
    """
    Test 10,000 concurrent HTTP requests to actual API
    
    This tests the full stack including FastAPI overhead.
    """
    print("\n" + "=" * 70)
    print("TEST 3: 10,000 Concurrent HTTP Requests (Full Stack)")
    print("=" * 70)
    print("\n⚠️  Server must be running: python run.py")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
    except:
        print("❌ Server not running! Start with: python run.py")
        return
    
    input("Press Enter to continue...")
    
    num_requests = 10000
    num_workers = 200
    
    tester = HighConcurrencyTest()
    
    # Get test auction ID
    try:
        response = requests.get(f"{BASE_URL}/auctions?limit=1")
        auctions = response.json()['auctions']
        if not auctions:
            print("❌ No auctions found!")
            return
        test_auction_id = auctions[0]['auction_id']
    except Exception as e:
        print(f"❌ Error getting auction: {e}")
        return
    
    print(f"📊 Configuration:")
    print(f"   Total Requests: {num_requests:,}")
    print(f"   Thread Pool Size: {num_workers}")
    print(f"   Test Auction ID: {test_auction_id}")
    print(f"   Endpoint: GET /auctions/{test_auction_id}")
    
    # Warm cache first
    print(f"\n🔥 Warming cache via API...")
    requests.post(f"{BASE_URL}/admin/cache/warm")
    
    def make_http_request(request_id: int):
        """Make HTTP request to API"""
        try:
            start = time.perf_counter()
            
            response = requests.get(
                f"{BASE_URL}/auctions/{test_auction_id}",
                timeout=30
            )
            
            elapsed = (time.perf_counter() - start) * 1000
            
            tester.record_result({
                "request_id": request_id,
                "response_time": elapsed,
                "success": response.status_code == 200,
                "status_code": response.status_code
            })
            
        except Exception as e:
            tester.record_error(str(e))
            tester.record_result({
                "request_id": request_id,
                "response_time": 0,
                "success": False,
                "status_code": 0
            })
    
    # Run test
    print(f"\n🚀 Starting {num_requests:,} concurrent HTTP requests...")
    print("Progress: ", end="", flush=True)
    
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        
        for i in range(num_requests):
            future = executor.submit(make_http_request, i)
            futures.append(future)
            
            # Show progress
            if (i + 1) % 1000 == 0:
                print(f"{i+1:,}...", end="", flush=True)
        
        # Wait for completion
        for future in as_completed(futures):
            pass
    
    total_time = (time.perf_counter() - start_time) * 1000
    
    print(" Done!")
    
    # Calculate statistics
    stats = tester.get_statistics()
    
    # Get cache stats via API
    try:
        cache_response = requests.get(f"{BASE_URL}/admin/cache-stats")
        cache_stats = cache_response.json()
    except:
        cache_stats = {}
    
    # Display results
    print("\n" + "─" * 70)
    print("📊 RESULTS - HTTP REQUESTS (FULL STACK):")
    print("─" * 70)
    print(f"Total Time:          {total_time:,.2f} ms ({total_time/1000:.2f} seconds)")
    print(f"Total Requests:      {stats['total_requests']:,}")
    print(f"Successful:          {stats['successful']:,}")
    print(f"Failed:              {stats['failed']:,}")
    print(f"Errors:              {stats['errors']:,}")
    print(f"\nResponse Times:")
    print(f"  Min:               {stats['min_time']:.2f} ms")
    print(f"  Max:               {stats['max_time']:.2f} ms")
    print(f"  Mean:              {stats['mean_time']:.2f} ms")
    print(f"  Median:            {stats['median_time']:.2f} ms")
    print(f"  95th Percentile:   {stats['p95_time']:.2f} ms")
    print(f"  99th Percentile:   {stats['p99_time']:.2f} ms")
    print(f"  Std Deviation:     {stats['stdev']:.2f} ms")
    print(f"\nThroughput:")
    print(f"  Requests/Second:   {(num_requests / (total_time/1000)):,.2f}")
    
    if cache_stats:
        print(f"\nCache Performance:")
        print(f"  Hit Rate:          {cache_stats.get('hit_rate', 'N/A')}")
    
    print("─" * 70)
    
    return {
        "total_time": total_time,
        "stats": stats,
        "cache_stats": cache_stats,
        "throughput": num_requests / (total_time/1000)
    }


# ============================================================================
# TEST 4: PROGRESSIVE LOAD TEST (Ramp Up)
# ============================================================================
def test_progressive_load():
    """
    Progressive load test - ramp up from 100 to 10,000 requests
    
    This shows how system performs under increasing load.
    """
    print("\n" + "=" * 70)
    print("TEST 4: Progressive Load Test (Ramp Up)")
    print("=" * 70)
    
    load_levels = [100, 500, 1000, 2000, 5000, 10000]
    
    results = {}
    
    db = SessionLocal()
    auction = db.query(Auction).filter(Auction.status == "ACTIVE").first()
    if not auction:
        print("❌ No active auction found.")
        return
    
    test_auction_id = auction.auction_id
    db.close()
    
    cache = get_cache_manager()
    
    # Warm cache
    db = SessionLocal()
    cache.get_auction(test_auction_id, db)
    db.close()
    
    print(f"\nTesting load levels: {', '.join(map(str, load_levels))}")
    print(f"Test Auction ID: {test_auction_id}\n")
    
    for load in load_levels:
        print(f"\n🔄 Testing {load:,} concurrent requests...")
        
        tester = HighConcurrencyTest()
        num_workers = min(load, 200)
        
        def make_request(request_id: int):
            db = SessionLocal()
            try:
                start = time.perf_counter()
                auction_data = cache.get_auction(test_auction_id, db)
                elapsed = (time.perf_counter() - start) * 1000
                
                tester.record_result({
                    "request_id": request_id,
                    "response_time": elapsed,
                    "success": auction_data is not None
                })
            except Exception as e:
                tester.record_error(str(e))
                tester.record_result({
                    "request_id": request_id,
                    "response_time": 0,
                    "success": False
                })
            finally:
                db.close()
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(make_request, i) for i in range(load)]
            for future in as_completed(futures):
                pass
        
        total_time = (time.perf_counter() - start_time) * 1000
        stats = tester.get_statistics()
        
        results[load] = {
            "total_time": total_time,
            "mean_response": stats['mean_time'],
            "p95_response": stats['p95_time'],
            "throughput": load / (total_time/1000),
            "success_rate": (stats['successful'] / stats['total_requests'] * 100)
        }
        
        print(f"   Total Time:    {total_time:,.2f} ms")
        print(f"   Mean Response: {stats['mean_time']:.2f} ms")
        print(f"   P95 Response:  {stats['p95_time']:.2f} ms")
        print(f"   Throughput:    {results[load]['throughput']:,.2f} req/s")
        print(f"   Success Rate:  {results[load]['success_rate']:.1f}%")
    
    # Summary table
    print("\n" + "=" * 70)
    print("📊 PROGRESSIVE LOAD TEST SUMMARY")
    print("=" * 70)
    print(f"{'Load':>10} | {'Total Time':>12} | {'Mean':>10} | {'P95':>10} | {'Throughput':>12} | {'Success':>8}")
    print("-" * 70)
    
    for load, data in results.items():
        print(f"{load:>10,} | {data['total_time']:>10,.0f} ms | "
              f"{data['mean_response']:>8,.2f} ms | {data['p95_response']:>8,.2f} ms | "
              f"{data['throughput']:>10,.0f}/s | {data['success_rate']:>6,.1f}%")
    
    print("=" * 70)
    
    return results


# ============================================================================
# TEST 5: COMPARISON TEST (Direct vs Cache)
# ============================================================================
def test_comparison_db_vs_cache():
    """
    Side-by-side comparison of DB vs Cache
    
    Both tests run 10K requests for fair comparison.
    """
    print("\n" + "=" * 70)
    print("TEST 5: Direct Comparison - Database vs Cache")
    print("=" * 70)
    print("\nThis test runs both scenarios back-to-back for comparison.\n")
    
    input("Press Enter to start comparison test...")
    
    print("\n" + "─" * 70)
    print("PART 1: Testing WITHOUT Cache")
    print("─" * 70)
    
    db_results = test_10k_concurrent_db_only()
    
    print("\n" + "─" * 70)
    print("PART 2: Testing WITH Cache")
    print("─" * 70)
    
    cache_results = test_10k_concurrent_with_cache()
    
    # Comparison
    if db_results and cache_results:
        speedup = db_results['total_time'] / cache_results['total_time']
        throughput_increase = cache_results['throughput'] / db_results['throughput']
        
        mean_speedup = db_results['stats']['mean_time'] / cache_results['stats']['mean_time']
        p95_speedup = db_results['stats']['p95_time'] / cache_results['stats']['p95_time']
        
        print("\n" + "=" * 70)
        print("🏆 FINAL COMPARISON")
        print("=" * 70)
        print(f"\nTotal Time:")
        print(f"  Without Cache: {db_results['total_time']:,.2f} ms ({db_results['total_time']/1000:.2f}s)")
        print(f"  With Cache:    {cache_results['total_time']:,.2f} ms ({cache_results['total_time']/1000:.2f}s)")
        print(f"  ⚡ Speedup:     {speedup:.1f}x faster!")
        
        print(f"\nMean Response Time:")
        print(f"  Without Cache: {db_results['stats']['mean_time']:.2f} ms")
        print(f"  With Cache:    {cache_results['stats']['mean_time']:.2f} ms")
        print(f"  ⚡ Speedup:     {mean_speedup:.1f}x faster!")
        
        print(f"\nP95 Response Time:")
        print(f"  Without Cache: {db_results['stats']['p95_time']:.2f} ms")
        print(f"  With Cache:    {cache_results['stats']['p95_time']:.2f} ms")
        print(f"  ⚡ Speedup:     {p95_speedup:.1f}x faster!")
        
        print(f"\nThroughput:")
        print(f"  Without Cache: {db_results['throughput']:,.2f} requests/second")
        print(f"  With Cache:    {cache_results['throughput']:,.2f} requests/second")
        print(f"  ⚡ Increase:    {throughput_increase:.1f}x more requests/second!")
        
        print(f"\nCache Hit Rate: {cache_results['cache_stats']['overall_hit_rate']:.1%}")
        
        print("\n" + "=" * 70)
        print("✅ Cache provides massive performance improvement!")
        print("=" * 70)


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def run_all_high_concurrency_tests():
    """Run all high concurrency tests"""
    print("\n" + "=" * 70)
    print("🚀 HIGH CONCURRENCY TEST SUITE (10,000 Requests)")
    print("=" * 70)
    print("\nAvailable Tests:")
    print("1. Database Only (No Cache)")
    print("2. With Cache")
    print("3. HTTP Requests (Full Stack)")
    print("4. Progressive Load Test")
    print("5. Full Comparison (DB vs Cache)")
    
    print("\nSelect test:")
    print("  1 - Database Only")
    print("  2 - With Cache")
    print("  3 - HTTP Requests")
    print("  4 - Progressive Load")
    print("  5 - Full Comparison (Recommended)")
    print("  A - Run All Tests")
    
    choice = input("\nYour choice (1-5 or A): ").strip().upper()
    
    if choice == "1":
        test_10k_concurrent_db_only()
    elif choice == "2":
        test_10k_concurrent_with_cache()
    elif choice == "3":
        test_10k_concurrent_http_requests()
    elif choice == "4":
        test_progressive_load()
    elif choice == "5":
        test_comparison_db_vs_cache()
    elif choice == "A":
        test_comparison_db_vs_cache()
        test_10k_concurrent_http_requests()
        test_progressive_load()
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    run_all_high_concurrency_tests()