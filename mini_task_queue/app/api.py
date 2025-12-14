from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
import json

from app.queue import queue
from app.models import Task, TaskSubmission, TaskResponse, TaskStatus
from app.config import settings
import asyncio
from datetime import datetime

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    print("🚀 Starting API server...")
    await queue.connect()
    
    # Check Redis connection
    if await queue.ping():
        print("✅ Redis connection OK")
    else:
        print("❌ Redis connection FAILED")
    
    yield
    
    # Shutdown
    print("👋 Shutting down API server...")
    await queue.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Mini-Celery Task Queue",
    description="Distributed task queue with real-time updates",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ HTTP Endpoints ============

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "mini-celery",
        "status": "running",
        "queue_length": await queue.get_queue_length()
    }


@app.post("/tasks", response_model=dict)
async def create_task(submission: TaskSubmission):
    """
    Submit a new task to the queue
    
    Request body:
    {
        "name": "add",
        "args": [1, 2],
        "kwargs": {}
    }
    
    Returns:
    {
        "task_id": "uuid-here",
        "status": "PENDING"
    }
    """
    # Create task
    task = Task(
        name=submission.name,
        args=submission.args,
        kwargs=submission.kwargs,
        max_retries=submission.max_retries
    )
    
    # Enqueue task
    try:
        task_id = await queue.enqueue_task(task)
        
        return {
            "task_id": task_id,
            "status": task.status.value,
            "max_retries": task.max_retries,
            "message": f"Task '{task.name}' submitted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {str(e)}")


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    Get task status and result
    
    Returns:
    {
        "task_id": "uuid",
        "status": "SUCCESS|FAILED|RUNNING|PENDING",
        "result": <any>,
        "error": <string|null>,
        "created_at": "timestamp",
        "updated_at": "timestamp"
    }
    """
    task = await queue.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        result=task.result,
        error=task.error,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task"""
    if not await queue.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    await queue.delete_task(task_id)
    
    return {
        "message": f"Task {task_id} deleted successfully"
    }


@app.get("/queue/stats")
async def queue_stats():
    """Get queue statistics"""
    return {
        "queue_length": await queue.get_queue_length(),
        "queue_name": queue.queue_name
    }
    
@app.get("/tasks")
async def list_tasks(limit: int = 10):
    """
    List recent tasks (note: this is inefficient for production)
    
    In production, you'd want to maintain a sorted set in Redis
    """
    # This is just for demo - not efficient for large scale
    # You'd need a proper index in production
    return {
        "message": "Task listing not implemented yet",
        "suggestion": "Use specific task IDs to query tasks"
    }


@app.post("/tasks/bulk", response_model=dict)
async def create_bulk_tasks(submissions: List[TaskSubmission]):
    """
    Submit multiple tasks at once
    
    Request body:
    [
        {"name": "add", "args": [1, 2]},
        {"name": "multiply", "args": [3, 4]}
    ]
    """
    tasks = [
        Task(name=sub.name, args=sub.args, kwargs=sub.kwargs)
        for sub in submissions
    ]
    
    # Use asyncio.gather for concurrent enqueuing
    task_ids = await asyncio.gather(*[
        queue.enqueue_task(task) for task in tasks
    ])
    
    return {
        "message": f"Submitted {len(task_ids)} tasks",
        "task_ids": task_ids
    }
    
@app.get("/queue/dead-letter")
async def get_dead_letter_queue():
    """Get tasks in dead-letter queue"""
    task_ids = await queue.get_dead_letter_tasks()
    
    # Get full task details
    tasks = []
    for task_id in task_ids:
        task = await queue.get_task(task_id)
        if task:
            tasks.append({
                "task_id": task.id,
                "name": task.name,
                "status": task.status,
                "error": task.error,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            })
    
    return {
        "count": len(tasks),
        "tasks": tasks
    }


@app.post("/tasks/{task_id}/retry")
async def manual_retry_task(task_id: str):
    """Manually retry a task from dead-letter queue"""
    task = await queue.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Reset retry count and requeue
    task.retry_count = 0
    task_key = f"task:{task_id}"
    await queue.redis.hset(task_key, mapping={
        "retry_count": "0",
        "status": TaskStatus.PENDING.value,
        "error": "",
        "updated_at": datetime.utcnow().isoformat()
    })
    
    # Add back to main queue
    await queue.redis.lpush(queue.queue_name, task_id)
    
    # Remove from dead-letter queue
    await queue.redis.lrem("queue:dead_letter", 0, task_id)
    
    return {
        "message": f"Task {task_id} requeued for retry",
        "task_id": task_id
    }
    
# ============ WebSocket Endpoint ============

@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_events(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task updates
    
    Client connects to: ws://localhost:8000/ws/tasks/{task_id}
    Receives JSON messages with task events
    """
    await websocket.accept()
    
    # Check if task exists
    if not await queue.task_exists(task_id):
        await websocket.send_json({
            "error": f"Task {task_id} not found"
        })
        await websocket.close()
        return
    
    # Subscribe to task events
    pubsub = await queue.subscribe_task_events(task_id)
    
    try:
        # Send initial task status
        task = await queue.get_task(task_id)
        await websocket.send_json({
            "event": "connected",
            "task_id": task_id,
            "current_status": task.status,
            "message": f"Subscribed to task {task_id}"
        })
        print(f"🔌 Client connected to task {task_id} events with status {task.status}")
        
        # Listen for events and forward to WebSocket
        async for message in pubsub.listen():
            if message["type"] == "message":
                # Parse the event data
                event_data = json.loads(message["data"].decode('utf-8'))
                
                # Send to WebSocket client
                await websocket.send_json(event_data)
                print(f"📨 Sent event to clients: {event_data}")
                
                # If task completed or failed, we can close
                if event_data.get("event") in ["completed", "failed"]:
                    print(f"👋 Task {task_id} finished, closing WebSocket")
                    await websocket.send_json({
                        "event": "stream_end",
                        "message": "Task finished, closing connection"
                    })
                    break
    
    except WebSocketDisconnect:
        print(f"🔌 Client disconnected from task {task_id}")
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        await websocket.send_json({
            "error": str(e)
        })
    
    finally:
        # Cleanup
        await pubsub.unsubscribe()
        await pubsub.close()
        print(f"👋 WebSocket closed for task {task_id}")