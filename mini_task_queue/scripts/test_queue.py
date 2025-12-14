import asyncio
from app.queue import queue
from app.models import Task, TaskStatus


async def test_queue():
    """Test Redis queue operations"""
    
    # Connect
    await queue.connect()
    
    # Test 1: Enqueue task
    print("\n--- Test 1: Enqueue Task ---")
    task = Task(name="add", args=[5, 3])
    task_id = await queue.enqueue_task(task)
    print(f"Task ID: {task_id}")
    
    # Test 2: Get task
    print("\n--- Test 2: Get Task ---")
    retrieved = await queue.get_task(task_id)
    print(f"Retrieved: {retrieved.name}, args={retrieved.args}, status={retrieved.status}")
    
    # Test 3: Queue length
    print("\n--- Test 3: Queue Length ---")
    length = await queue.get_queue_length()
    print(f"Queue length: {length}")
    
    # Test 4: Pop task
    print("\n--- Test 4: Pop Task ---")
    popped_id = await queue.pop_task(timeout=2)
    print(f"Popped task ID: {popped_id}")
    
    # Test 5: Update status
    print("\n--- Test 5: Update Status ---")
    await queue.set_task_status(task_id, TaskStatus.RUNNING)
    updated = await queue.get_task(task_id)
    print(f"Updated status: {updated.status}")
    
    # Test 6: Set result
    print("\n--- Test 6: Set Result ---")
    await queue.set_task_status(task_id, TaskStatus.SUCCESS, result=8)
    completed = await queue.get_task(task_id)
    print(f"Final status: {completed.status}, result: {completed.result}")
    
    # Test 7: Publish event
    print("\n--- Test 7: Publish Event ---")
    await queue.publish_event(task_id, "test_event", {"message": "Hello!"})
    
    # Cleanup
    await queue.delete_task(task_id)
    await queue.disconnect()
    
    print("\n✅ All queue tests passed!")


if __name__ == "__main__":
    asyncio.run(test_queue())