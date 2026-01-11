"""Retry utilities with exponential backoff.

This module provides retry logic for handling transient failures when
sending data to the ingestion API. It implements exponential backoff
to avoid overwhelming the service during outages.
"""
import asyncio
import random
from typing import Any, Callable, Optional, TypeVar

from observability.common.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles each retry)
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff (default: 2)
        jitter: Add randomness to prevent thundering herd (default: True)
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds before next retry
            
        Example:
            With initial_delay=1.0, exponential_base=2.0:
            - attempt 0: 1.0s
            - attempt 1: 2.0s
            - attempt 2: 4.0s
            - attempt 3: 8.0s
        """
        # Calculate exponential delay: initial * (base ^ attempt)
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        # All clients retrying at exact same time can overwhelm the server
        if self.jitter:
            # Add random factor between 0 and 0.3 * delay
            jitter_amount = random.uniform(0, 0.3 * delay)
            delay += jitter_amount
        
        return delay


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    config: Optional[RetryConfig] = None,
    retry_on_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    """Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration (uses defaults if None)
        retry_on_exceptions: Tuple of exception types to retry on
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from successful function call
        
    Raises:
        The last exception if all retries fail
        
    Example:
        ```python
        async def send_data(data):
            # Might fail with network error
            await http_client.post("/api/logs", json=data)
        
        # Automatically retries on failure
        await retry_async(send_data, data=my_logs)
        ```
    """
    if config is None:
        config = RetryConfig()
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            # Try to execute the function
            result = await func(*args, **kwargs)
            
            # Success!
            if attempt > 0:
                logger.info(
                    "Retry succeeded",
                    function=func.__name__,
                    attempt=attempt,
                )
            
            return result
            
        except retry_on_exceptions as e:
            last_exception = e
            
            # If this was the last attempt, give up
            if attempt >= config.max_retries:
                logger.error(
                    "All retries exhausted",
                    function=func.__name__,
                    total_attempts=attempt + 1,
                    error=str(e),
                )
                raise
            
            # Calculate delay before next retry
            delay = config.get_delay(attempt)
            
            logger.warning(
                "Operation failed, retrying",
                function=func.__name__,
                attempt=attempt + 1,
                max_retries=config.max_retries,
                delay_seconds=round(delay, 2),
                error=str(e),
            )
            
            # Wait before retrying
            await asyncio.sleep(delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error")


def retry_sync(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    retry_on_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> T:
    """Retry a synchronous function with exponential backoff.
    
    Same as retry_async but for non-async functions.
    
    Args:
        func: Function to retry
        *args: Positional arguments for func
        config: Retry configuration
        retry_on_exceptions: Tuple of exception types to retry on
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from successful function call
        
    Raises:
        The last exception if all retries fail
    """
    import time
    
    if config is None:
        config = RetryConfig()
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            result = func(*args, **kwargs)
            
            if attempt > 0:
                logger.info(
                    "Retry succeeded",
                    function=func.__name__,
                    attempt=attempt,
                )
            
            return result
            
        except retry_on_exceptions as e:
            last_exception = e
            
            if attempt >= config.max_retries:
                logger.error(
                    "All retries exhausted",
                    function=func.__name__,
                    total_attempts=attempt + 1,
                    error=str(e),
                )
                raise
            
            delay = config.get_delay(attempt)
            
            logger.warning(
                "Operation failed, retrying",
                function=func.__name__,
                attempt=attempt + 1,
                max_retries=config.max_retries,
                delay_seconds=round(delay, 2),
                error=str(e),
            )
            
            time.sleep(delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error")


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures.
    
    If a service is down, stop trying to call it for a while (circuit is "open").
    After a timeout, try again (circuit is "half-open").
    If it works, resume normal operation (circuit is "closed").
    
    This prevents wasting resources on a service that's clearly down.
    
    States:
        - CLOSED: Normal operation, requests go through
        - OPEN: Service is down, fail fast without trying
        - HALF_OPEN: Testing if service is back up
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            expected_exception: Exception type that counts as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result from function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        import time
        
        # If circuit is open, check if we should try again
        if self.state == "OPEN":
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time >= self.recovery_timeout
            ):
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering half-open state")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            
            # Success! Reset failure count
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                logger.info("Circuit breaker closed")
            
            self.failure_count = 0
            return result
            
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    "Circuit breaker opened",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold,
                )
            
            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass