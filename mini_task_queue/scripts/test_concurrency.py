import asyncio
from app.queue import queue
from app.models import Task


async def test_concurrency():
    """Submit multiple tasks to test concurrent processing"""
    
    await queue.connect()
    
    # Submit 10 sleep tasks that take 2 seconds each
    # With 5 workers, should complete in ~4 seconds (not 20!)
    print("📤 Submitting 10 tasks (2 seconds each)...")
    
    tasks = [Task(name="sleep", args=[2]) for _ in range(10)]
    
    # Use asyncio.gather for bulk submission
    task_ids = await asyncio.gather(*[
        queue.enqueue_task(task) for task in tasks
    ])
    
    print(f"✅ Submitted {len(task_ids)} tasks")
    print(f"   With 5 workers, should complete in ~4 seconds")
    print(f"\n🏃 Start worker now: python -m app.worker")
    
    await queue.disconnect()


if __name__ == "__main__":
    asyncio.run(test_concurrency())