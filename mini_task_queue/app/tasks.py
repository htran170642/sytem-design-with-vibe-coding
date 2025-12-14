import asyncio
from typing import Any


# Task Registry - maps task names to functions
TASK_REGISTRY = {}


def register_task(name: str):
    """Decorator to register a task function"""
    def decorator(func):
        TASK_REGISTRY[name] = func
        return func
    return decorator


# ============ Example Tasks ============

@register_task("add")
async def add(a: int, b: int) -> int:
    """Add two numbers"""
    print(f"[task][add]  ➕ Adding {a} + {b}")
    await asyncio.sleep(0.5)  # Simulate some work
    return a + b


@register_task("multiply")
async def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    print(f"[task][multiply]  ✖️  Multiplying {a} × {b}")
    await asyncio.sleep(0.5)
    return a * b


@register_task("sleep")
async def sleep_task(seconds: int) -> str:
    """Sleep for N seconds"""
    print(f"[task][sleep]  😴 Sleeping for {seconds} seconds...")
    await asyncio.sleep(seconds)
    return f"Slept for {seconds} seconds"


@register_task("failing_task")
async def failing_task(message: str) -> None:
    """A task that always fails - for testing error handling"""
    print(f"[task][failing_task]  💥 About to fail with: {message}")
    await asyncio.sleep(0.2)
    raise ValueError(f"Task failed: {message}")


@register_task("long_task")
async def long_task(steps: int) -> str:
    """
    A task that takes multiple steps and reports progress
    Used to demonstrate event publishing
    """
    print(f"[task][long_task]  🏃 Starting long task with {steps} steps")
    for i in range(1, steps + 1):
        await asyncio.sleep(1)
        print(f"[task][long_task]    Step {i}/{steps} completed")
        # Worker will publish progress events
    return f"Completed {steps} steps"


def get_task_function(name: str):
    """Get task function by name"""
    if name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {name}")
    return TASK_REGISTRY[name]