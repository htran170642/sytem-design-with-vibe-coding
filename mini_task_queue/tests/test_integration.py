import pytest
import asyncio
from app.models import Task, TaskStatus
from app.worker import Worker
from app.tasks import TASK_REGISTRY


@pytest.mark.asyncio
async def test_full_task_lifecycle(redis_queue):
    """Test complete task lifecycle: submit -> process -> complete"""
    
    # Submit task
    task = Task(name="add", args=[10, 20])
    task_id = await redis_queue.enqueue_task(task)
    
    # Verify task is in queue
    assert await redis_queue.task_exists(task_id)
    
    # Start a worker in background
    worker = Worker(concurrency=1)
    
    # Create worker task but don't await it yet
    async def run_worker():
        try:
            await worker.start()
        except Exception as e:
            print(f"Worker error: {e}")
    
    worker_task = asyncio.create_task(run_worker())
    
    # Wait a bit for worker to connect
    await asyncio.sleep(1)
    
    # Wait for task to be processed (max 5 seconds)
    for i in range(50):
        task = await redis_queue.get_task(task_id)
        if task.status == TaskStatus.SUCCESS:
            break
        await asyncio.sleep(0.1)
    
    # Stop worker gracefully
    worker.running = False
    worker.shutdown_event.set()
    
    # Wait for worker to stop
    try:
        await asyncio.wait_for(worker_task, timeout=3.0)
    except asyncio.TimeoutError:
        print("Worker shutdown timeout")
    except Exception as e:
        print(f"Worker shutdown error: {e}")
    
    # Verify result
    final_task = await redis_queue.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.SUCCESS
    assert final_task.result == 30


@pytest.mark.asyncio
async def test_task_retry_then_success(redis_queue):
    """Test task that fails once then succeeds"""
    
    # Create a counter to track attempts
    test_key = "test:retry_counter"
    await redis_queue.redis.set(test_key, "0")
    
    # Define a custom task that fails first time
    async def flaky_task():
        counter_bytes = await redis_queue.redis.get(test_key)
        counter = int(counter_bytes.decode('utf-8')) if counter_bytes else 0
        await redis_queue.redis.incr(test_key)
        
        if counter == 0:
            raise ValueError("First attempt fails")
        return "success"
    
    # Temporarily add to registry
    original_task = TASK_REGISTRY.get("flaky_task")
    TASK_REGISTRY["flaky_task"] = flaky_task
    
    try:
        # Submit task
        task = Task(name="flaky_task", args=[], max_retries=3)
        task_id = await redis_queue.enqueue_task(task)
        
        # Start worker
        worker = Worker(concurrency=1)
        
        async def run_worker():
            try:
                await worker.start()
            except Exception as e:
                print(f"Worker error: {e}")
        
        worker_task = asyncio.create_task(run_worker())
        await asyncio.sleep(1)
        
        # Wait for task to complete (should retry once then succeed)
        for i in range(100):
            task = await redis_queue.get_task(task_id)
            if task.status == TaskStatus.SUCCESS:
                break
            await asyncio.sleep(0.1)
        
        # Stop worker
        worker.running = False
        worker.shutdown_event.set()
        
        try:
            await asyncio.wait_for(worker_task, timeout=3.0)
        except asyncio.TimeoutError:
            print("Worker shutdown timeout")
        
        # Verify
        final_task = await redis_queue.get_task(task_id)
        assert final_task is not None
        assert final_task.status == TaskStatus.SUCCESS
        assert final_task.retry_count == 1  # Failed once, succeeded on retry
        assert final_task.result == "success"
        
    finally:
        # Cleanup
        await redis_queue.redis.delete(test_key)
        if original_task:
            TASK_REGISTRY["flaky_task"] = original_task
        else:
            TASK_REGISTRY.pop("flaky_task", None)


@pytest.mark.asyncio
async def test_concurrent_task_processing(redis_queue):
    """Test multiple tasks processed concurrently"""
    
    # Submit 5 sleep tasks
    task_ids = []
    for i in range(5):
        task = Task(name="sleep", args=[1])  # 1 second each
        task_id = await redis_queue.enqueue_task(task)
        task_ids.append(task_id)
    
    # Start worker with 5 concurrent workers
    import time
    start_time = time.time()
    
    worker = Worker(concurrency=5)
    
    async def run_worker():
        try:
            await worker.start()
        except Exception as e:
            print(f"Worker error: {e}")
    
    worker_task = asyncio.create_task(run_worker())
    await asyncio.sleep(1)
    
    # Wait for all tasks to complete
    all_complete = False
    for attempt in range(60):  # 6 seconds max
        statuses = []
        for tid in task_ids:
            task = await redis_queue.get_task(tid)
            if task:
                statuses.append(task.status)
        
        if len(statuses) == 5 and all(s == TaskStatus.SUCCESS for s in statuses):
            all_complete = True
            break
        
        await asyncio.sleep(0.1)
    
    elapsed = time.time() - start_time
    
    # Stop worker
    worker.running = False
    worker.shutdown_event.set()
    
    try:
        await asyncio.wait_for(worker_task, timeout=3.0)
    except asyncio.TimeoutError:
        print("Worker shutdown timeout")
    
    # With 5 concurrent workers, 5 tasks of 1 second each should take ~1-2 seconds
    # (not 5 seconds sequentially)
    assert all_complete, f"Not all tasks completed. Elapsed: {elapsed}s"
    assert elapsed < 4.0, f"Tasks took {elapsed}s, should be < 4s with concurrency"