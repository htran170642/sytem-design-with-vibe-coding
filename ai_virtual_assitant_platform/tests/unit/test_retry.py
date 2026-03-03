"""
Tests for Retry Utilities
"""

import pytest
import asyncio
from unittest.mock import Mock
from openai import RateLimitError, APITimeoutError

from app.utils.retry import (
    retry_with_exponential_backoff,
    with_timeout,
    TimeoutManager,
)


def create_mock_openai_error(error_class, message="Test error"):
    """Create a properly formed OpenAI error for testing"""
    mock_response = Mock()
    mock_response.status_code = 429 if error_class == RateLimitError else 500
    mock_body = {"error": {"message": message}}
    return error_class(message, response=mock_response, body=mock_body)


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt():
    """Test that retry decorator doesn't interfere with successful calls"""
    
    @retry_with_exponential_backoff(max_retries=3)
    async def successful_function():
        return "success"
    
    result = await successful_function()
    assert result == "success"
    print("✓ Successful call works without retries")


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    """Test that function succeeds after retrying"""
    
    attempt_count = 0
    
    @retry_with_exponential_backoff(max_retries=3, initial_delay=0.1)
    async def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        
        # Fail first 2 times, succeed on 3rd
        if attempt_count < 3:
            raise create_mock_openai_error(RateLimitError, "Rate limit exceeded")
        return "success"
    
    result = await flaky_function()
    
    assert result == "success"
    assert attempt_count == 3  # Failed twice, succeeded on 3rd
    print(f"✓ Function succeeded after {attempt_count} attempts")


@pytest.mark.asyncio
async def test_retry_exhausts_max_retries():
    """Test that retry gives up after max attempts"""
    
    attempt_count = 0
    
    @retry_with_exponential_backoff(max_retries=2, initial_delay=0.1)
    async def always_fails():
        nonlocal attempt_count
        attempt_count += 1
        raise create_mock_openai_error(RateLimitError, "Always fails")
    
    with pytest.raises(RateLimitError):
        await always_fails()
    
    assert attempt_count == 3  # Initial + 2 retries
    print(f"✓ Gave up after {attempt_count} attempts (1 initial + 2 retries)")


@pytest.mark.asyncio
async def test_retry_non_retryable_error():
    """Test that non-retryable errors fail immediately"""
    
    attempt_count = 0
    
    @retry_with_exponential_backoff(max_retries=3)
    async def raises_value_error():
        nonlocal attempt_count
        attempt_count += 1
        raise ValueError("Not a retryable error")
    
    with pytest.raises(ValueError):
        await raises_value_error()
    
    assert attempt_count == 1  # Should fail immediately, no retries
    print("✓ Non-retryable error fails immediately (no retries)")


@pytest.mark.asyncio
async def test_timeout_manager_success():
    """Test timeout manager with successful operation"""
    
    async with TimeoutManager(timeout=1.0, operation_name="test_op") as tm:
        await asyncio.sleep(0.1)
        result = "completed"
    
    assert result == "completed"
    print("✓ Timeout manager allows successful operations")


@pytest.mark.asyncio
async def test_with_timeout_success():
    """Test with_timeout utility function"""
    
    async def quick_operation():
        await asyncio.sleep(0.1)
        return "done"
    
    result = await with_timeout(
        quick_operation(),
        timeout=1.0,
        operation_name="quick_op"
    )
    
    assert result == "done"
    print("✓ with_timeout allows successful operations")


@pytest.mark.asyncio
async def test_with_timeout_exceeds():
    """Test with_timeout raises on timeout"""
    
    async def slow_operation():
        await asyncio.sleep(1.0)
        return "done"
    
    with pytest.raises(asyncio.TimeoutError):
        await with_timeout(
            slow_operation(),
            timeout=0.1,
            operation_name="slow_op"
        )
    
    print("✓ with_timeout raises TimeoutError on timeout")


@pytest.mark.asyncio
async def test_exponential_backoff_delays():
    """Test that delays increase exponentially"""
    
    delays = []
    
    @retry_with_exponential_backoff(
        max_retries=3,
        initial_delay=0.1,
        exponential_base=2.0,
        jitter=False  # Disable jitter for predictable testing
    )
    async def track_delays():
        import time
        if not hasattr(track_delays, 'last_time'):
            track_delays.last_time = time.time()
        else:
            current_time = time.time()
            delay = current_time - track_delays.last_time
            delays.append(delay)
            track_delays.last_time = current_time
        
        if len(delays) < 3:
            raise create_mock_openai_error(RateLimitError, "Retry me")
        return "done"
    
    await track_delays()
    
    # Check delays are increasing (approximately)
    assert len(delays) == 3
    assert delays[0] < delays[1] < delays[2]
    print(f"✓ Delays increase exponentially: {[round(d, 2) for d in delays]}")