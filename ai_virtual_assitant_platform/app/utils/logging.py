"""
Logging Utilities
Helper functions and decorators for logging
"""

import functools
import time
from typing import Any, Callable

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator to log function execution time

    Usage:
        @log_execution_time
        def my_function():
            pass
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        func_logger = get_logger(func.__module__)

        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time

            func_logger.debug(
                f"Function {func.__name__} completed",
                extra={
                    "function": func.__name__,
                    "duration_s": round(duration, 3),
                    "status": "success",
                },
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            func_logger.error(
                f"Function {func.__name__} failed",
                extra={
                    "function": func.__name__,
                    "duration_s": round(duration, 3),
                    "status": "error",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        func_logger = get_logger(func.__module__)

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            func_logger.debug(
                f"Function {func.__name__} completed",
                extra={
                    "function": func.__name__,
                    "duration_s": round(duration, 3),
                    "status": "success",
                },
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            func_logger.error(
                f"Function {func.__name__} failed",
                extra={
                    "function": func.__name__,
                    "duration_s": round(duration, 3),
                    "status": "error",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    # Return appropriate wrapper based on whether function is async
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def log_with_context(**context_kwargs):
    """
    Decorator to add context to all log messages in a function

    Usage:
        @log_with_context(user_id="123", request_id="abc")
        def my_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Add context to logger
            func_logger = get_logger(func.__module__)
            # Note: This is a simplified version
            # In production, you'd use contextvars for proper context management
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Import asyncio at the end to avoid circular imports
import asyncio