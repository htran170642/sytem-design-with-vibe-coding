import pytest
from app.models import Task, TaskStatus
from app.queue import queue


@pytest.mark.asyncio
async def test_enqueue_and_pop_task(redis_queue):
    """Test basic enqueue and pop operations"""
    # Create and enqueue task
    task = Task(name="add", args=[1, 2])
    task_id = await redis_queue.enqueue_task(task)
    
    assert task_id == task.id
    
    # Check queue length
    length = await redis_queue.get_queue_length()
    assert length == 1
    
    # Pop task
    popped_id = await redis_queue.pop_task(timeout=1)
    assert popped_id == task_id
    
    # Queue should be empty now
    length = await redis_queue.get_queue_length()
    assert length == 0


@pytest.mark.asyncio
async def test_get_task(redis_queue):
    """Test retrieving task details"""
    # Enqueue task
    task = Task(name="multiply", args=[3, 4], kwargs={"verbose": True})
    task_id = await redis_queue.enqueue_task(task)
    
    # Retrieve task
    retrieved = await redis_queue.get_task(task_id)
    
    assert retrieved is not None
    assert retrieved.id == task_id
    assert retrieved.name == "multiply"
    assert retrieved.args == [3, 4]
    assert retrieved.kwargs == {"verbose": True}
    assert retrieved.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_set_task_status(redis_queue):
    """Test updating task status"""
    # Create task
    task = Task(name="add", args=[5, 7])
    task_id = await redis_queue.enqueue_task(task)
    
    # Update to RUNNING
    await redis_queue.set_task_status(task_id, TaskStatus.RUNNING)
    task = await redis_queue.get_task(task_id)
    assert task.status == TaskStatus.RUNNING
    
    # Update to SUCCESS with result
    await redis_queue.set_task_status(task_id, TaskStatus.SUCCESS, result=12)
    task = await redis_queue.get_task(task_id)
    assert task.status == TaskStatus.SUCCESS
    assert task.result == 12


@pytest.mark.asyncio
async def test_requeue_task(redis_queue):
    """Test retry mechanism"""
    # Create task
    task = Task(name="failing_task", args=["test"], max_retries=3)
    task_id = await redis_queue.enqueue_task(task)
    
    # Pop and fail it
    await redis_queue.pop_task(timeout=1)
    
    # Requeue for retry
    success = await redis_queue.requeue_task(task_id)
    assert success is True
    
    # Check retry count increased
    task = await redis_queue.get_task(task_id)
    assert task.retry_count == 1
    
    # Check it's back in queue
    length = await redis_queue.get_queue_length()
    assert length == 1


@pytest.mark.asyncio
async def test_dead_letter_queue(redis_queue):
    """Test dead-letter queue functionality"""
    # Create task
    task = Task(name="failing_task", args=["test"], max_retries=2)
    task_id = await redis_queue.enqueue_task(task)
    
    # Move to dead-letter queue
    await redis_queue.move_to_dead_letter(task_id)
    
    # Check it's in dead-letter queue
    dlq_tasks = await redis_queue.get_dead_letter_tasks()
    assert task_id in dlq_tasks
    
    # Check status updated
    task = await redis_queue.get_task(task_id)
    assert task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_task_not_found(redis_queue):
    """Test handling of non-existent tasks"""
    task = await redis_queue.get_task("non-existent-id")
    assert task is None
    
    exists = await redis_queue.task_exists("non-existent-id")
    assert exists is False


@pytest.mark.asyncio
async def test_pop_task_timeout(redis_queue):
    """Test pop with timeout when queue is empty"""
    # Try to pop from empty queue with 1 second timeout
    import time
    start = time.time()
    
    result = await redis_queue.pop_task(timeout=1)
    
    elapsed = time.time() - start
    
    assert result is None
    assert 0.9 < elapsed < 1.5  # Should wait approximately 1 second