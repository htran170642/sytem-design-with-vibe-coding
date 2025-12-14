import asyncio
from app.queue import queue
from app.models import Task


async def submit_test_tasks():
    """Submit some test tasks to the queue"""
    
    await queue.connect()
    
    # Submit various tasks
    tasks = [
        Task(name="add", args=[10, 20]),
        Task(name="multiply", args=[5, 6]),
        Task(name="sleep", args=[2]),
        Task(name="long_task", args=[3]),
        Task(name="failing_task", args=["intentional error"]),
    ]
    
    print("📤 Submitting tasks...")
    for task in tasks:
        task_id = await queue.enqueue_task(task)
        print(f"  Submitted: {task.name} → {task_id[:8]}")
    
    await queue.disconnect()
    print("\n✅ All tasks submitted! Now start the worker in another terminal:")
    print("   python -m app.worker")


if __name__ == "__main__":
    asyncio.run(submit_test_tasks())