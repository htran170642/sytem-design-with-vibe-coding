import asyncio
import time
from app.queue import queue
from app.models import Task


async def benchmark():
    """Quick performance benchmark"""
    
    await queue.connect()
    await queue.redis.flushdb()
    
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK")
    print("="*60 + "\n")
    
    # Prepare tasks
    num_tasks = 1000
    tasks = [Task(name="add", args=[i, i+1]) for i in range(num_tasks)]
    
    # Test 1: Sequential enqueue (small sample)
    print("Test 1: Sequential Enqueue Performance")
    start = time.time()
    for task in tasks[:100]:
        await queue.enqueue_task(task)
    seq_time = time.time() - start
    print(f"  100 tasks: {seq_time:.3f}s ({100/seq_time:.0f} ops/sec)\n")
    
    # Test 2: Batched concurrent enqueue
    print("Test 2: Batched Concurrent Enqueue")
    
    batch_size = 20
    remaining_tasks = tasks[100:]
    batches = [remaining_tasks[i:i+batch_size] for i in range(0, len(remaining_tasks), batch_size)]
    
    start = time.time()
    for batch in batches:
        await asyncio.gather(*[queue.enqueue_task(task) for task in batch])
    batched_time = time.time() - start
    
    print(f"  {len(remaining_tasks)} tasks: {batched_time:.3f}s ({len(remaining_tasks)/batched_time:.0f} ops/sec)")
    print(f"  Batch size: {batch_size}")
    print(f"  Speedup vs sequential: {(seq_time*len(remaining_tasks)/100)/batched_time:.1f}x\n")
    
    # Test 3: Pop performance
    print("Test 3: Pop Performance")
    start = time.time()
    popped_ids = []
    for _ in range(100):
        task_id = await queue.pop_task(timeout=0)
        if task_id:
            popped_ids.append(task_id)
    pop_time = time.time() - start
    print(f"  {len(popped_ids)} pops: {pop_time:.3f}s ({len(popped_ids)/pop_time:.0f} ops/sec)\n")
    
    # Test 4: Get task performance
    print("Test 4: Get Task Performance")
    
    # Get IDs to fetch
    get_ids = popped_ids[:50] if len(popped_ids) >= 50 else popped_ids
    
    start = time.time()
    for tid in get_ids:
        await queue.get_task(tid)
    get_time = time.time() - start
    print(f"  {len(get_ids)} gets: {get_time:.3f}s ({len(get_ids)/get_time:.0f} ops/sec)\n")
    
    # Test 5: Concurrent get with batching
    print("Test 5: Batched Concurrent Get")
    
    batch_size = 10
    get_batches = [get_ids[i:i+batch_size] for i in range(0, len(get_ids), batch_size)]
    
    start = time.time()
    for batch in get_batches:
        await asyncio.gather(*[queue.get_task(tid) for tid in batch])
    batch_get_time = time.time() - start
    
    print(f"  {len(get_ids)} gets: {batch_get_time:.3f}s ({len(get_ids)/batch_get_time:.0f} ops/sec)")
    print(f"  Speedup: {get_time/batch_get_time:.1f}x\n")
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Enqueue (batched):   {len(remaining_tasks)/batched_time:.0f} ops/sec")
    print(f"Pop:                 {len(popped_ids)/pop_time:.0f} ops/sec")
    print(f"Get (sequential):    {len(get_ids)/get_time:.0f} ops/sec")
    print(f"Get (batched):       {len(get_ids)/batch_get_time:.0f} ops/sec")
    print(f"\nConnection pool size: 50")
    print(f"Batch size used: {batch_size}")
    
    await queue.disconnect()


if __name__ == "__main__":
    asyncio.run(benchmark())