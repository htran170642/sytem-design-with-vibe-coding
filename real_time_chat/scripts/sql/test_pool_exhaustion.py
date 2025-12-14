"""
Test what happens when connection pool is exhausted
"""


import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


from database import engine, get_pool_status
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError
import concurrent.futures
import time

def long_running_query(query_id, sleep_time=5):
    """
    Simulate a slow query that holds a connection
    
    Args:
        query_id: ID of this query
        sleep_time: How long to hold the connection
    """
    try:
        print(f"[Query {query_id}] Requesting connection...")
        start = time.time()
        
        # CHECK-OUT connection
        conn = engine.connect()
        checkout_time = time.time() - start
        
        status = get_pool_status()
        print(f"[Query {query_id}] Got connection after {checkout_time:.2f}s "
              f"(checked-out: {status['checked_out']}, overflow: {status['overflow']})")
        
        # Hold the connection for sleep_time seconds (simulating slow query)
        conn.execute(text(f"SELECT pg_sleep({sleep_time})"))
        
        # CHECK-IN connection
        conn.close()
        
        total_time = time.time() - start
        print(f"[Query {query_id}] ✅ Completed in {total_time:.2f}s")
        
        return {"query_id": query_id, "success": True, "time": total_time}
        
    except TimeoutError as e:
        elapsed = time.time() - start
        print(f"[Query {query_id}] ❌ TIMEOUT after {elapsed:.2f}s - Pool exhausted!")
        return {"query_id": query_id, "success": False, "error": "TimeoutError"}
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"[Query {query_id}] ❌ ERROR after {elapsed:.2f}s: {e}")
        return {"query_id": query_id, "success": False, "error": str(e)}


def test_pool_exhaustion():
    """
    Test pool exhaustion by creating more requests than pool capacity
    
    Pool config:
    - pool_size = 20
    - max_overflow = 10
    - Total capacity = 30
    - pool_timeout = 30 seconds
    """
    print("\n" + "="*70)
    print("POOL EXHAUSTION TEST")
    print("="*70)
    print(f"Pool configuration:")
    print(f"  - pool_size: 20")
    print(f"  - max_overflow: 10")
    print(f"  - Total capacity: 30")
    print(f"  - pool_timeout: 30 seconds")
    print("="*70)
    
    # Initial status
    status = get_pool_status()
    print(f"\nInitial pool status:")
    print(f"  Checked-in:  {status['checked_in']}")
    print(f"  Checked-out: {status['checked_out']}")
    print(f"  Overflow:    {status['overflow']}")
    
    # Create 35 concurrent slow queries (more than pool capacity of 30)
    num_queries = 35
    sleep_time = 3  # Each query takes 3 seconds
    
    print(f"\n→ Starting {num_queries} concurrent queries (each takes {sleep_time}s)...")
    print(f"→ Expected: First 30 succeed, last 5 wait or timeout\n")
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor to run queries concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_queries) as executor:
        # Submit all queries at once
        futures = [
            executor.submit(long_running_query, i, sleep_time)
            for i in range(1, num_queries + 1)
        ]
        
        # Wait for all to complete
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    total_time = time.time() - start_time
    
    # Analyze results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"Total queries:       {num_queries}")
    print(f"Successful:          {len(successful)}")
    print(f"Failed (timeout):    {len(failed)}")
    print(f"Total time:          {total_time:.2f}s")
    
    if failed:
        print(f"\nFailed queries:")
        for r in failed:
            print(f"  - Query {r['query_id']}: {r['error']}")
    
    # Final pool status
    status = get_pool_status()
    print(f"\nFinal pool status:")
    print(f"  Checked-in:  {status['checked_in']}")
    print(f"  Checked-out: {status['checked_out']}")
    print(f"  Overflow:    {status['overflow']}")
    
    print("\n" + "="*70)
    print("EXPLANATION:")
    print("  • First 20 queries: Used pool connections")
    print("  • Queries 21-30:    Used overflow connections")
    print("  • Queries 31-35:    Waited for available connections")
    print("  • If wait > 30s:    TimeoutError raised")
    print("="*70 + "\n")


def test_what_happens_on_timeout():
    """
    Test what actually happens when timeout occurs
    """
    print("\n" + "="*70)
    print("TIMEOUT BEHAVIOR TEST")
    print("="*70)
    
    print("\nScenario: 31 queries, each takes 35 seconds (longer than timeout)")
    print("Expected: First 30 succeed, 31st times out after 30 seconds\n")
    
    # This will definitely timeout
    num_queries = 31
    sleep_time = 35  # Longer than pool_timeout (30s)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_queries) as executor:
        futures = [
            executor.submit(long_running_query, i, sleep_time)
            for i in range(1, num_queries + 1)
        ]
        
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\nSuccessful: {len(successful)}")
    print(f"Timed out:  {len(failed)}")


if __name__ == "__main__":
    import sys
    
    print("\n1) Test pool exhaustion (35 queries, capacity 30)")
    print("2) Test timeout behavior (queries longer than timeout)")
    
    choice = input("\nChoice (1 or 2): ")
    
    if choice == "1":
        test_pool_exhaustion()
    elif choice == "2":
        test_what_happens_on_timeout()
    else:
        print("Invalid choice")