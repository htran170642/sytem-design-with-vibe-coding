"""
Retry Utilities
Implements retry logic with exponential backoff for LLM calls
Phase 3, Step 2: Implement retry & timeout logic
"""

import asyncio
import time
from functools import wraps
from typing import Callable, Type, Tuple, Optional

from openai import (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Errors that should trigger a retry
RETRYABLE_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_ERRORS,
):
    """
    Decorator to retry async functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Tuple of exceptions that trigger retry
        
    Example:
        @retry_with_exponential_backoff(max_retries=3)
        async def call_api():
            return await client.chat.completions.create(...)
    """
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # Try to execute the function
                    return await func(*args, **kwargs)
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry if we've exhausted all attempts
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempts": attempt + 1,
                                "error": str(e),
                            },
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter: random value between 0 and delay
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Retrying {func.__name__} after {delay:.2f}s (attempt {attempt + 1}/{max_retries})",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_seconds": round(delay, 2),
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )
                    
                    # Wait before retrying
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    # Non-retryable exception - raise immediately
                    logger.error(
                        f"Non-retryable error in {func.__name__}",
                        extra={
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class TimeoutManager:
    """
    Context manager for timeout handling
    
    Usage:
        async with TimeoutManager(timeout=30) as tm:
            result = await some_long_operation()
    """
    
    def __init__(self, timeout: float, operation_name: str = "operation"):
        """
        Initialize timeout manager
        
        Args:
            timeout: Timeout in seconds
            operation_name: Name for logging
        """
        self.timeout = timeout
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
        
    async def __aenter__(self):
        """Start timing"""
        self.start_time = time.time()
        logger.debug(
            f"Starting {self.operation_name} with {self.timeout}s timeout",
            extra={
                "operation": self.operation_name,
                "timeout_seconds": self.timeout,
            },
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Log completion time"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            
            if exc_type is asyncio.TimeoutError:
                logger.error(
                    f"{self.operation_name} timed out after {elapsed:.2f}s",
                    extra={
                        "operation": self.operation_name,
                        "elapsed_seconds": round(elapsed, 2),
                        "timeout_seconds": self.timeout,
                    },
                )
            else:
                logger.debug(
                    f"{self.operation_name} completed in {elapsed:.2f}s",
                    extra={
                        "operation": self.operation_name,
                        "elapsed_seconds": round(elapsed, 2),
                    },
                )
        
        return False  # Don't suppress exceptions


async def with_timeout(coro, timeout: float, operation_name: str = "operation"):
    """
    Execute coroutine with timeout
    
    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        operation_name: Name for logging
        
    Returns:
        Result of coroutine
        
    Raises:
        asyncio.TimeoutError: If operation times out
        
    Example:
        result = await with_timeout(
            client.chat.completions.create(...),
            timeout=30,
            operation_name="chat_completion"
        )
    """
    async with TimeoutManager(timeout, operation_name):
        return await asyncio.wait_for(coro, timeout=timeout)