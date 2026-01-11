"""Ingestion service for receiving logs and metrics from agents.

This module contains the FastAPI application that accepts log and metric
batches from collection agents, validates them, and writes them to Kafka.
"""

__version__ = "0.1.0"

__all__ = [
    # FastAPI app
    "app",
    # Authentication
    "verify_api_key",
    "AuthenticationError",
    # Rate limiting
    "check_rate_limit",
    "RateLimitExceeded",
    "rate_limiter",
    # Kafka producer
    "get_producer",
    "close_producer",
    "MockKafkaProducer",
]

# Import components
try:
    from observability.ingestion.auth import AuthenticationError, verify_api_key
    from observability.ingestion.kafka_producer import (
        MockKafkaProducer,
        close_producer,
        get_producer,
    )
    from observability.ingestion.main import app
    from observability.ingestion.rate_limiter import (
        RateLimitExceeded,
        check_rate_limit,
        rate_limiter,
    )
except ImportError:
    # Files not created yet
    pass