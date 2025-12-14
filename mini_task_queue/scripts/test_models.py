from app.models import Task, TaskStatus, TaskSubmission
from app.utils import task_to_redis, create_event
import json


def test_task_creation():
    """Test basic task creation"""
    task = Task(name="add", args=[1, 2])
    print(f"✅ Task created: {task.id}")
    print(f"   Status: {task.status}")
    print(f"   Name: {task.name}")
    print(f"   Args: {task.args}")
    

def test_task_serialization():
    """Test Redis serialization"""
    task = Task(name="sleep", args=[5], kwargs={"verbose": True})
    redis_data = task_to_redis(task)
    print(f"\n✅ Redis hash format:")
    for key, value in redis_data.items():
        print(f"   {key}: {value}")


def test_event_creation():
    """Test event message creation"""
    event = create_event("started", {"task_id": "123"})
    print(f"\n✅ Event message:")
    print(f"   {json.dumps(json.loads(event), indent=2)}")


if __name__ == "__main__":
    test_task_creation()
    test_task_serialization()
    test_event_creation()
    print("\n✅ All model tests passed!")