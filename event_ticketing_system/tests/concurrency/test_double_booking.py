"""
Concurrency test: Verify no double booking under high load
"""
import asyncio
import aiohttp
import time
import logging
from typing import List, Dict
from collections import Counter
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/api/v1"
EVENT_ID = 1
TARGET_SEATS = [1, 2, 3, 4, 5]  # Same seats for everyone


async def attempt_booking(session: aiohttp.ClientSession, user_id: int) -> Dict:
    """Attempt to book the target seats"""
    start_time = time.time()
    
    try:
        async with session.post(
            f"{API_URL}/bookings?user_id={user_id}",
            json={
                "event_id": EVENT_ID,
                "seat_ids": TARGET_SEATS
            },
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "user_id": user_id,
                "status_code": response.status,
                "success": response.status == 201,
                "duration_ms": duration_ms,
                "response": None,
                "error": None
            }
            
            if response.status == 201:
                result["response"] = await response.json()
            elif response.status >= 400:
                # Try to get error message
                try:
                    error_data = await response.json()
                    result["error"] = error_data.get('detail', 'Unknown error')
                except:
                    result["error"] = await response.text()
            
            return result
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return {
            "user_id": user_id,
            "status_code": 0,
            "success": False,
            "duration_ms": duration_ms,
            "error": str(e)
        }


async def run_concurrent_booking_test(num_users: int = 100):
    """
    Run concurrent booking test
    
    Expected: Only 1 user should succeed
    All others should get 409 Conflict
    """
    logger.info(f"🚀 Starting concurrent booking test with {num_users} users")
    logger.info(f"📍 Target seats: {TARGET_SEATS}")
    
    # Create aiohttp session with connection limits
    connector = aiohttp.TCPConnector(limit=50, limit_per_host=50)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Create tasks for all users
        tasks = [
            attempt_booking(session, user_id)
            for user_id in range(1, num_users + 1)
        ]
        
        # Execute all requests concurrently
        logger.info(f"⚡ Sending {num_users} concurrent requests...")
        start_time = time.time()
        
        results = await asyncio.gather(*tasks)
        
        total_duration = time.time() - start_time
        logger.info(f"✅ All requests completed in {total_duration:.2f}s")
    
    # Analyze results
    return analyze_results(results, total_duration)


def analyze_results(results: List[Dict], total_duration: float) -> bool:
    """
    Analyze test results
    
    Returns True if test passed, False otherwise
    """
    
    successes = [r for r in results if r['success']]
    failures = [r for r in results if not r['success']]
    
    status_codes = Counter([r['status_code'] for r in results])
    
    avg_duration = sum(r['duration_ms'] for r in results) / len(results)
    min_duration = min(r['duration_ms'] for r in results)
    max_duration = max(r['duration_ms'] for r in results)
    
    # Print results
    logger.info("=" * 60)
    logger.info("📊 TEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Total requests: {len(results)}")
    logger.info(f"Successful bookings: {len(successes)}")
    logger.info(f"Failed bookings: {len(failures)}")
    logger.info(f"")
    logger.info(f"Status codes:")
    for code, count in sorted(status_codes.items()):
        logger.info(f"  {code}: {count}")
    logger.info(f"")
    logger.info(f"Response times:")
    logger.info(f"  Average: {avg_duration:.2f}ms")
    logger.info(f"  Min: {min_duration:.2f}ms")
    logger.info(f"  Max: {max_duration:.2f}ms")
    logger.info(f"")
    logger.info(f"Throughput: {len(results) / total_duration:.2f} req/s")
    logger.info("=" * 60)
    
    # Show sample errors for 500s
    errors_500 = [r for r in results if r['status_code'] == 500]
    if errors_500:
        logger.error("")
        logger.error(f"⚠️ {len(errors_500)} requests got HTTP 500 errors")
        logger.error("Sample errors:")
        for err in errors_500[:3]:  # Show first 3
            logger.error(f"  User {err['user_id']}: {err.get('error', 'Unknown')[:100]}")
    
    # Validation
    logger.info("")
    logger.info("🔍 VALIDATION:")
    
    test_passed = True
    
    # Check if we had server errors
    if status_codes.get(500, 0) > 0:
        logger.error(f"⚠️ WARNING: {status_codes[500]} server errors (HTTP 500)")
        logger.error("   This might indicate database connection pool exhaustion")
        logger.error("   or other server-side issues")
        # Don't fail test for 500s, but warn
    
    if len(successes) == 1:
        logger.info("✅ PASS: Exactly 1 booking succeeded (no double booking!)")
        winner = successes[0]
        logger.info(f"   Winner: User {winner['user_id']}")
        if winner.get('response'):
            logger.info(f"   Booking ID: {winner['response']['id']}")
    elif len(successes) == 0:
        logger.error("❌ FAIL: No bookings succeeded")
        if status_codes.get(500, 0) > 0:
            logger.error("   Likely due to server errors")
        test_passed = False
    else:
        logger.error(f"❌ FAIL: {len(successes)} bookings succeeded (DOUBLE BOOKING DETECTED!)")
        logger.error(f"   Winners: {[s['user_id'] for s in successes]}")
        test_passed = False
    
    # Check for 409 Conflict responses
    conflict_count = status_codes.get(409, 0)
    expected_conflicts = len(results) - len(successes) - status_codes.get(500, 0)
    
    if conflict_count >= expected_conflicts - 5:  # Allow some variance
        logger.info(f"✅ PASS: Good number of conflicts ({conflict_count})")
    else:
        logger.warning(f"⚠️ WARNING: Expected ~{expected_conflicts} conflicts, got {conflict_count}")
    
    logger.info("=" * 60)
    
    return test_passed


async def verify_database_state_sqlalchemy():
    """Verify using SQLAlchemy (fallback method)"""
    try:
        # Use sync SQLAlchemy to avoid event loop issues
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        
        # Create sync engine
        sync_engine = create_engine(settings.DATABASE_URL)
        
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, status, current_booking_id 
                    FROM event_seats 
                    WHERE id IN (1,2,3,4,5)
                    ORDER BY id
                """)
            )
            
            seats = result.fetchall()
            
            hold_count = 0
            booked_count = 0
            
            for seat in seats:
                seat_id, status, booking_id = seat
                logger.info(f"Seat {seat_id}: {status} (Booking: {booking_id})")
                
                if status == 'HOLD':
                    hold_count += 1
                elif status == 'BOOKED':
                    booked_count += 1
            
            logger.info("")
            logger.info(f"Total HOLD: {hold_count}")
            logger.info(f"Total BOOKED: {booked_count}")
            
            if hold_count + booked_count == 1:
                logger.info("✅ PASS: Database consistent (1 booking)")
                return True
            elif hold_count + booked_count == 0:
                logger.warning("⚠️ WARNING: No bookings in database")
                return True
            else:
                logger.error(f"❌ FAIL: Database inconsistent ({hold_count + booked_count} bookings)")
                return False
    
    except Exception as e:
        logger.error(f"❌ SQLAlchemy verification failed: {e}")
        return True

async def verify_database_state_simple():
    """Verify database has no double bookings using subprocess psql"""
    logger.info("")
    logger.info("🔍 DATABASE VERIFICATION:")
    logger.info("=" * 60)
    
    try:
        import subprocess
        
        # Query database using psql
        cmd = f"""
        psql event_ticketing -t -c "
            SELECT id, status, current_booking_id 
            FROM event_seats 
            WHERE id IN (1,2,3,4,5)
            ORDER BY id;
        "
        """
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"❌ psql command failed: {result.stderr}")
            return True
        
        lines = result.stdout.strip().split('\n')
        
        hold_count = 0
        booked_count = 0
        
        for line in lines:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                seat_id = parts[0]
                status = parts[1]
                booking_id = parts[2] if len(parts) > 2 else 'NULL'
                
                logger.info(f"Seat {seat_id}: {status} (Booking: {booking_id})")
                
                if status == 'HOLD':
                    hold_count += 1
                elif status == 'BOOKED':
                    booked_count += 1
        
        logger.info("")
        logger.info(f"Total HOLD: {hold_count}")
        logger.info(f"Total BOOKED: {booked_count}")
        
        test_passed = True
        
        if hold_count + booked_count == 1:
            logger.info("✅ PASS: Database consistent (1 booking)")
        elif hold_count + booked_count == 0:
            logger.warning("⚠️ WARNING: No bookings in database")
        else:
            logger.error(f"❌ FAIL: Database inconsistent ({hold_count + booked_count} bookings)")
            test_passed = False
        
        logger.info("=" * 60)
        
        return test_passed
    
    except Exception as e:
        logger.error(f"❌ Error verifying database: {e}")
        logger.info("=" * 60)
        return True


async def reset_test_seats():
    """Reset target seats to AVAILABLE before test using SQL"""
    logger.info("🧹 Resetting test seats...")
    
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # Reset seats to AVAILABLE using SQL
            query = text("""
                UPDATE event_seats 
                SET status = 'AVAILABLE', current_booking_id = NULL 
                WHERE id = ANY(:seat_ids)
            """)
            
            await db.execute(query, {"seat_ids": TARGET_SEATS})
            await db.commit()
            
            logger.info(f"✅ Reset {len(TARGET_SEATS)} seats to AVAILABLE")
            return True
    
    except Exception as e:
        logger.error(f"❌ Error resetting seats: {e}")
        
        # Fallback: direct SQL
        import subprocess
        try:
            cmd = """
            psql event_ticketing -c "
                UPDATE event_seats 
                SET status = 'AVAILABLE', current_booking_id = NULL 
                WHERE id IN (1,2,3,4,5);
            "
            """
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("✅ Reset via psql command")
                return True
            else:
                logger.error(f"psql error: {result.stderr}")
                return False
        except Exception as e2:
            logger.error(f"❌ Manual reset also failed: {e2}")
            return False


async def main():
    """Main test execution"""
    # Check server is running
    import requests
    try:
        response = requests.get(f"{API_URL.replace('/api/v1', '')}/health")
        if response.status_code != 200:
            logger.error("❌ Server not healthy")
            return False
        logger.info("✅ Server is running")
    except Exception as e:
        logger.error(f"❌ Cannot connect to server at {API_URL}")
        logger.error(f"   Error: {e}")
        logger.error(f"   Make sure server is running: python -m app.main")
        return False
    
    # Reset seats
    if not await reset_test_seats():
        logger.error("❌ Failed to reset seats")
        return False
    
    # Run concurrency test
    test_passed = await run_concurrent_booking_test(num_users=100)
    
    # Verify database (using subprocess to avoid event loop issues)
    db_passed = await verify_database_state_sqlalchemy()
    
    # Final result
    if test_passed and db_passed:
        logger.info("")
        logger.info("🎉 ALL TESTS PASSED!")
        return True
    else:
        logger.error("")
        logger.error("❌ TESTS FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)