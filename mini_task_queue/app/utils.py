import json
from typing import Any, Dict
from datetime import datetime
from app.models import Task, TaskStatus


def task_to_redis(task: Task) -> Dict[str, str]:
    """Convert Task object to Redis hash format (all strings)"""
    return {
        "id": task.id,
        "name": task.name,
        "args": json.dumps(task.args),
        "kwargs": json.dumps(task.kwargs),
        "status": task.status if isinstance(task.status, str) else task.status.value,
        "result": json.dumps(task.result) if task.result is not None else "",
        "error": task.error or "",
        "max_retries": str(task.max_retries),
        "retry_count": str(task.retry_count),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "processing_started_at": task.processing_started_at.isoformat() if task.processing_started_at else "",
    }


def redis_to_task(data: Dict[bytes, bytes]) -> Task:
    """Convert Redis hash to Task object"""
    decoded = {k.decode(): v.decode() for k, v in data.items()}
    
    return Task(
        id=decoded["id"],
        name=decoded["name"],
        args=json.loads(decoded["args"]),
        kwargs=json.loads(decoded["kwargs"]),
        status=decoded["status"],
        result=json.loads(decoded["result"]) if decoded["result"] else None,
        error=decoded["error"] or None,
        max_retries=int(decoded.get("max_retries", 3)),
        retry_count=int(decoded.get("retry_count", 0)),
        created_at=datetime.fromisoformat(decoded["created_at"]),
        updated_at=datetime.fromisoformat(decoded["updated_at"]),
        processing_started_at=datetime.fromisoformat(decoded["processing_started_at"]) if decoded.get("processing_started_at") else None,
    )


def create_event(event_type: str, data: Any = None) -> str:
    """Create a JSON event message for Pub/Sub"""
    event = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data or {}
    }
    return json.dumps(event)