"""
Logging Examples
Demonstrates various logging patterns used in AIVA
"""

from app.core.logging_config import get_logger, log_error, log_llm_request, log_request

# Get module-specific logger
logger = get_logger(__name__)


def example_basic_logging():
    """Basic logging examples"""
    logger.debug("Debug message - detailed information for debugging")
    logger.info("Info message - general informational messages")
    logger.warning("Warning message - something unexpected happened")
    logger.error("Error message - something failed")
    logger.critical("Critical message - serious error")


def example_structured_logging():
    """Structured logging with extra context"""
    # Add structured data to logs
    logger.info(
        "User action",
        extra={
            "user_id": "user_123",
            "action": "document_upload",
            "document_id": "doc_456",
            "file_size": 1024000,
        },
    )


def example_http_request_logging():
    """Log HTTP requests"""
    # Using the convenience function
    log_request(
        logger,
        method="POST",
        path="/api/documents",
        status_code=201,
        duration=0.234,  # seconds
    )


def example_llm_request_logging():
    """Log LLM API requests with token usage"""
    log_llm_request(
        logger,
        model="gpt-3.5-turbo",
        prompt_tokens=150,
        completion_tokens=200,
        duration=1.5,
    )


def example_error_logging():
    """Log errors with context"""
    try:
        # Simulate an error
        result = 1 / 0
    except Exception as e:
        log_error(
            logger,
            error=e,
            context={
                "operation": "division",
                "user_id": "user_123",
                "request_id": "req_789",
            },
        )


async def example_async_function():
    """Example async function with logging"""
    logger.info("Starting async operation")

    # Simulate async work
    import asyncio

    await asyncio.sleep(0.1)

    logger.info("Async operation completed")


def main():
    """Run all examples"""
    logger.info("=== Starting Logging Examples ===")

    example_basic_logging()
    example_structured_logging()
    example_http_request_logging()
    example_llm_request_logging()
    example_error_logging()

    logger.info("=== Logging Examples Complete ===")


if __name__ == "__main__":
    main()