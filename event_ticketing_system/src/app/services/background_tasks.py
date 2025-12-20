"""
Background tasks manager for long-running workers
"""
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks like auto-admission workers"""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.running: Dict[str, bool] = {}
    
    def start_task(self, name: str, coroutine, *args, **kwargs):
        """Start a background task"""
        if name in self.tasks and not self.tasks[name].done():
            logger.warning(f"Task {name} already running")
            return
        
        self.running[name] = True
        task = asyncio.create_task(coroutine(*args, **kwargs))
        self.tasks[name] = task
        
        logger.info(f"✅ Started background task: {name}")
        
        # Add callback to handle completion
        task.add_done_callback(lambda t: self._task_done_callback(name, t))
    
    def stop_task(self, name: str):
        """Stop a background task"""
        if name in self.tasks:
            self.running[name] = False
            self.tasks[name].cancel()
            logger.info(f"🛑 Stopped background task: {name}")
    
    def _task_done_callback(self, name: str, task: asyncio.Task):
        """Handle task completion"""
        try:
            exception = task.exception()
            if exception:
                logger.error(f"❌ Task {name} failed: {exception}")
        except asyncio.CancelledError:
            logger.info(f"✅ Task {name} cancelled")
        finally:
            self.running[name] = False
    
    def is_running(self, name: str) -> bool:
        """Check if task is running"""
        return self.running.get(name, False)
    
    async def shutdown_all(self):
        """Shutdown all background tasks"""
        logger.info("🛑 Shutting down all background tasks...")
        
        for name in list(self.tasks.keys()):
            self.stop_task(name)
        
        # Wait for all tasks to complete
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        
        logger.info("✅ All background tasks stopped")


# Global instance
task_manager = BackgroundTaskManager()