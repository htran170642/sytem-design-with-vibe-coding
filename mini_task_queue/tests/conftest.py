import pytest
import pytest_asyncio
import asyncio
from app.queue import RedisQueue


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def redis_queue():
    """Setup and teardown Redis connection for each test"""
    # Create a fresh queue instance for each test
    test_queue = RedisQueue()
    await test_queue.connect()
    
    # Clean up any existing test data
    await test_queue.redis.flushdb()
    
    yield test_queue
    
    # Cleanup after test
    try:
        await test_queue.redis.flushdb()
        await test_queue.disconnect()
    except Exception as e:
        print(f"Cleanup error: {e}")