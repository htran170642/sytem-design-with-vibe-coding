"""
Celery Configuration
Background task processing with Celery
Phase 5: Background Jobs & Async Processing
"""

from celery import Celery
from kombu import Queue

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "aiva",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Reject if worker dies
    worker_prefetch_multiplier=1,  # Process one task at a time
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,  # Persist results in Redis
    
    # Retry settings
    task_default_retry_delay=60,  # Wait 60s before retry
    task_max_retries=3,  # Max 3 retries
    
    # # Task routing
    # task_routes={
    #     "app.tasks.document_tasks.*": {"queue": "documents"},
    #     "app.tasks.ai_tasks.*": {"queue": "ai"},
    # },
    
    # # Queues
    # task_queues=(
    #     Queue("default", routing_key="default"),
    #     Queue("documents", routing_key="documents"),
    #     Queue("ai", routing_key="ai"),
    # ),
    
    # Worker settings
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    
    # Monitoring
    task_send_sent_event=True,  # Send task-sent events
    worker_send_task_events=True,  # Send task events
)

# Task autodiscovery
celery_app.autodiscover_tasks(["app.tasks"])

# Celery beat schedule (for periodic tasks)
celery_app.conf.beat_schedule = {
    # Example: Clean up old tasks every day
    "cleanup-old-tasks": {
        "task": "app.tasks.maintenance.cleanup_old_tasks",
        "schedule": 86400.0,  # Every 24 hours
    },
}