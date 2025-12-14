import asyncio
import time
import statistics
from app.queue import queue
from app.models import Task


async def load_test_submission(num_tasks: int = 100):
    """Test bulk task submission performance"""
    
    print(f"\n{'='*60}")
    print(f"LOAD TEST: Submitting {num_tasks} tasks")
    print(f"{'='*60}\n")
    
    await queue.connect()
    
    # Cleanup
    await queue.redis.flushdb()
    
    # Prepare tasks
    tasks = [Task(name="add", args=[i, i+1]) for i in range(num_tasks)]
    
    # Test sequential submission
    print("Test 1: Sequential submission")
    start = time.time()
    for task in tasks[:10]:  # Just 10 for sequential
        await queue.enqueue_task(task)
    sequential_time = time.time() - start
    print(f"  ⏱️  10 tasks: {sequential_time:.3f}s ({10/sequential_time:.1f} tasks/sec)")
    
    # Test concurrent submission with batching (to avoid connection pool limits)
    print("\nTest 2: Concurrent submission with batching (asyncio.gather)")
    
    batch_size = 20  # Process 20 tasks at a time
    batches = [tasks[i:i+batch_size] for i in range(0, len(tasks), batch_size)]
    
    start = time.time()
    for batch in batches:
        await asyncio.gather(*[
            queue.enqueue_task(task) for task in batch
        ])
    concurrent_time = time.time() - start
    
    print(f"  ⏱️  {num_tasks} tasks: {concurrent_time:.3f}s ({num_tasks/concurrent_time:.1f} tasks/sec)")
    print(f"  📦 Batch size: {batch_size}")
    print(f"  🚀 Speedup: {(sequential_time*num_tasks/10)/concurrent_time:.1f}x faster")
    
    # Verify queue length
    length = await queue.get_queue_length()
    print(f"\n✅ Queue length: {length} (expected {num_tasks + 10})")
    
    await queue.disconnect()


async def load_test_processing(num_tasks: int = 50, num_workers: int = 5):
    """Test task processing throughput"""
    
    print(f"\n{'='*60}")
    print(f"LOAD TEST: Processing {num_tasks} tasks with {num_workers} workers")
    print(f"{'='*60}\n")
    
    await queue.connect()
    await queue.redis.flushdb()
    
    # Submit tasks (mix of quick and slow)
    print(f"Submitting {num_tasks} tasks...")
    tasks = []
    for i in range(num_tasks):
        if i % 3 == 0:
            task = Task(name="sleep", args=[0.1])  # Fast task
        else:
            task = Task(name="add", args=[i, i+1])  # Instant task
        tasks.append(task)
    
    task_ids = await asyncio.gather(*[
        queue.enqueue_task(task) for task in tasks
    ])
    print(f"✅ Submitted {len(task_ids)} tasks\n")
    
    # Start workers
    from app.worker import Worker
    
    print(f"Starting {num_workers} workers...")
    worker = Worker(concurrency=num_workers)
    worker_task = asyncio.create_task(worker.start())
    
    await asyncio.sleep(1)  # Let workers initialize
    
    # Monitor progress
    start_time = time.time()
    last_completed = 0
    
    print("\nProcessing progress:")
    while True:
        # Count completed tasks
        completed = 0
        for tid in task_ids:
            task = await queue.get_task(tid)
            if task and task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED]:
                completed += 1
        
        elapsed = time.time() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        
        if completed > last_completed:
            print(f"  {completed}/{num_tasks} tasks ({completed/num_tasks*100:.1f}%) - {rate:.1f} tasks/sec")
            last_completed = completed
        
        if completed == num_tasks:
            break
        
        await asyncio.sleep(0.5)
    
    total_time = time.time() - start_time
    
    # Stop workers
    worker.running = False
    worker.shutdown_event.set()
    try:
        await asyncio.wait_for(worker_task, timeout=3.0)
    except asyncio.TimeoutError:
        pass
    
    # Results
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total tasks: {num_tasks}")
    print(f"Workers: {num_workers}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {num_tasks/total_time:.1f} tasks/sec")
    print(f"Avg time per task: {total_time/num_tasks*1000:.1f}ms")
    
    await queue.disconnect()


async def load_test_retry_performance():
    """Test retry mechanism under load"""
    
    print(f"\n{'='*60}")
    print("LOAD TEST: Retry mechanism")
    print(f"{'='*60}\n")
    
    await queue.connect()
    await queue.redis.flushdb()
    
    # Submit failing tasks with different retry limits
    num_tasks = 20
    print(f"Submitting {num_tasks} failing tasks...")
    
    task_ids = []
    for i in range(num_tasks):
        task = Task(
            name="failing_task",
            args=[f"test {i}"],
            max_retries=2  # Will fail 3 times total
        )
        task_id = await queue.enqueue_task(task)
        task_ids.append(task_id)
    
    print(f"✅ Submitted {len(task_ids)} tasks\n")
    
    # Start workers
    from app.worker import Worker
    worker = Worker(concurrency=3)
    worker_task = asyncio.create_task(worker.start())
    await asyncio.sleep(1)
    
    # Monitor retries and dead-letter queue
    print("Monitoring retry progress:")
    start_time = time.time()
    
    while True:
        # Check task statuses
        retry_counts = {}
        failed_count = 0
        
        for tid in task_ids:
            task = await queue.get_task(tid)
            if task:
                retry_counts[tid] = task.retry_count
                if task.status == TaskStatus.FAILED:
                    failed_count += 1
        
        dlq_count = len(await queue.get_dead_letter_tasks())
        
        elapsed = time.time() - start_time
        
        print(f"  t={elapsed:.1f}s: Failed={failed_count}/{num_tasks}, DLQ={dlq_count}")
        
        if failed_count == num_tasks:
            break
        
        await asyncio.sleep(1)
    
    total_time = time.time() - start_time
    
    # Stop workers
    worker.running = False
    worker.shutdown_event.set()
    try:
        await asyncio.wait_for(worker_task, timeout=3.0)
    except asyncio.TimeoutError:
        pass
    
    # Results
    print(f"\n{'='*60}")
    print("RETRY RESULTS")
    print(f"{'='*60}")
    print(f"Total tasks: {num_tasks}")
    print(f"All tasks failed: {failed_count}/{num_tasks}")
    print(f"Dead-letter queue: {dlq_count}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Expected attempts: {num_tasks * 3} (each task tried 3 times)")
    
    await queue.disconnect()


if __name__ == "__main__":
    from app.models import TaskStatus
    
    print("\n🔥 MINI-CELERY LOAD TESTS 🔥\n")
    
    # Run all load tests
    asyncio.run(load_test_submission(num_tasks=100))
    # asyncio.run(load_test_processing(num_tasks=50, num_workers=5))
    # asyncio.run(load_test_retry_performance())
    
    print("\n✅ All load tests completed!\n")