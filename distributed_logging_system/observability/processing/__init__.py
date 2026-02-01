"""Stream processing module.

This module contains Kafka consumers that process logs and metrics
from Kafka topics, transform them, and prepare them for storage.
"""

from observability.processing.base_consumer import BaseConsumer
from observability.processing.log_processor import LogProcessor
from observability.processing.metrics_processor import MetricsProcessor

__all__ = [
    "BaseConsumer",
    "LogProcessor",
    "MetricsProcessor",
]