import asyncio
import signal
from typing import Optional
from datetime import datetime

from app.queue import queue
from app.models import TaskStatus
from app.tasks import get_task_function


class Worker:
    """Async task worker that processes tasks from Redis queue"""
    
    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency
        self.running = False
        self.tasks = []  # Background worker tasks
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the worker with N concurrent worker loops"""
        self.running = True
        
        # Connect to Redis
        await queue.connect()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        print(f"[worker-main] 🚀 Starting {self.concurrency} worker(s)...")
        
        # Start N worker coroutines
        self.tasks = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(self.concurrency)
        ]
        
        # Wait for all workers to complete
        await asyncio.gather(*self.tasks)
        
        # Cleanup
        await queue.disconnect()
        print("👋 Worker shutdown complete")
    
    def _setup_signal_handlers(self):
        """Setup handlers for SIGINT and SIGTERM"""
        def signal_handler(sig, frame):
            print(f"\n⚠️ [worker] Received signal {sig}, initiating graceful shutdown...")
            self.running = False
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _worker_loop(self, worker_id: int):
        """
        Main worker loop - runs forever until shutdown
        
        Pattern: Blocking pop with timeout to check shutdown signal
        """
        print(f"[worker-{worker_id}]   Worker-{worker_id} ready")
        
        while self.running:
            try:
                # Pop task with short timeout so we can check shutdown frequently
                task_id = await queue.pop_task(timeout=2)
                
                if task_id:
                    await self._handle_task(task_id, worker_id)
                
            except Exception as e:
                print(f"[worker-{worker_id}] ❌ Worker-{worker_id} error: {e}")
                await asyncio.sleep(1)  # Back off on error
        
        print(f"[worker]   Worker-{worker_id} stopped")
    
    async def _handle_task(self, task_id: str, worker_id: int):
        """
        Handle a single task execution with retry logic
        """
        print(f" \n[worker-{worker_id}]🔧 Worker-{worker_id} processing task {task_id[:8]}...")
        
        # Get task details
        task = await queue.get_task(task_id)
        if not task:
            print(f"[worker-{worker_id}] ⚠️  Task {task_id} not found")
            return
        
        # Update status to RUNNING and mark processing started
        await queue.set_task_status(task_id, TaskStatus.RUNNING)
        await queue.set_processing_started(task_id)
        
        await queue.publish_event(
            task_id, 
            "started", 
            {
                "worker_id": worker_id, 
                "task_name": task.name,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries
            }
        )
        
        try:
            # Get task function
            task_func = get_task_function(task.name)
            
            # Execute task
            start_time = datetime.utcnow()
            
            # Special handling for long_task to publish progress
            if task.name == "long_task":
                result = await self._execute_long_task(task_id, task_func, task.args, task.kwargs, worker_id)
            else:
                result = await task_func(*task.args, **task.kwargs)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Update status to SUCCESS
            await queue.set_task_status(task_id, TaskStatus.SUCCESS, result=result)
            await queue.publish_event(
                task_id,
                "completed",
                {
                    "result": result,
                    "duration": duration,
                    "worker_id": worker_id,
                    "retry_count": task.retry_count
                }
            )
            
            print(f"[worker-{worker_id}] ✅ Worker-{worker_id} completed task {task_id[:8]} in {duration:.2f}s")
        
        except Exception as e:
            # Task failed - decide whether to retry or move to dead-letter
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            # Check if we should retry
            if task.retry_count < task.max_retries:
                # Retry the task
                await queue.publish_event(
                    task_id,
                    "retry",
                    {
                        "error": error_msg,
                        "retry_count": task.retry_count + 1,
                        "max_retries": task.max_retries,
                        "worker_id": worker_id
                    }
                )
                
                await queue.requeue_task(task_id)
                
                print(f"[worker-{worker_id}] 🔄 Worker-{worker_id} task {task_id[:8]} failed, retrying ({task.retry_count + 1}/{task.max_retries})")
            else:
                # Max retries exceeded - move to dead-letter queue
                await queue.set_task_status(task_id, TaskStatus.FAILED, error=error_msg)
                await queue.move_to_dead_letter(task_id)
                
                await queue.publish_event(
                    task_id,
                    "failed",
                    {
                        "error": error_msg,
                        "worker_id": worker_id,
                        "retry_count": task.retry_count,
                        "moved_to_dead_letter": True
                    }
                )
                
                print(f"[worker-{worker_id}] 💀 Worker-{worker_id} task {task_id[:8]} failed permanently: {error_msg}")
            
    async def _execute_long_task(self, task_id: str, task_func, args, kwargs, worker_id: int):
        """
        Execute long_task with progress updates
        
        This demonstrates publishing intermediate progress events
        """
        steps = args[0] if args else kwargs.get('steps', 5)
        
        for i in range(1, steps + 1):
            await asyncio.sleep(1)
            
            # Publish progress event
            await queue.publish_event(
                task_id,
                "progress",
                {
                    "step": i,
                    "total_steps": steps,
                    "progress_percent": (i / steps) * 100,
                    "message": f"Step {i}/{steps} completed",
                    "worker_id": worker_id
                }
            )
            print(f"[worker-{worker_id}]     📊 Progress: {i}/{steps}")
        
        return f"Completed {steps} steps"


async def main():
    """Main entry point"""
    from app.config import settings
    
    worker = Worker(concurrency=settings.worker_concurrency)
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())