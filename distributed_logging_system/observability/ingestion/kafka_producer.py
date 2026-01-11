"""Kafka producer for the ingestion service.

This module provides a Kafka producer to write logs and metrics to Kafka topics.
Includes a mock implementation for testing without Kafka.
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from observability.common.config import get_settings
from observability.common.logger import get_logger
from observability.common.models import LogBatch, MetricBatch

logger = get_logger(__name__)


class ProducerError(Exception):
    """Raised when Kafka producer encounters an error."""
    pass


class BaseProducer(ABC):
    """Abstract base class for Kafka producers.
    
    This allows us to swap between real Kafka and mock implementations.
    """

    @abstractmethod
    async def send_logs(self, batch: LogBatch) -> None:
        """Send log batch to Kafka.
        
        Args:
            batch: Log batch to send
            
        Raises:
            ProducerError: If send fails
        """
        pass

    @abstractmethod
    async def send_metrics(self, batch: MetricBatch) -> None:
        """Send metric batch to Kafka.
        
        Args:
            batch: Metric batch to send
            
        Raises:
            ProducerError: If send fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the producer and cleanup resources."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush any pending messages."""
        pass


class MockKafkaProducer(BaseProducer):
    """Mock Kafka producer for testing without Kafka.
    
    This implementation:
    - Logs messages instead of sending to Kafka
    - Stores messages in memory for testing
    - Simulates Kafka behavior
    
    Perfect for:
    - Local development
    - Testing
    - CI/CD pipelines
    """

    def __init__(self):
        """Initialize mock producer."""
        self.logs_sent: List[Dict[str, Any]] = []
        self.metrics_sent: List[Dict[str, Any]] = []
        self.is_closed = False
        
        logger.info("Mock Kafka producer initialized (no actual Kafka connection)")

    async def send_logs(self, batch: LogBatch) -> None:
        """Mock send log batch.
        
        Args:
            batch: Log batch to send
            
        Raises:
            ProducerError: If producer is closed
        """
        if self.is_closed:
            raise ProducerError("Producer is closed")
        
        # Convert Pydantic model to dict
        batch_dict = batch.model_dump(mode="json")
        
        # Store in memory
        self.logs_sent.append(batch_dict)
        
        # Log the action
        logger.info(
            "Mock: Log batch sent to Kafka",
            topic="logs.raw",
            num_logs=len(batch.entries),
            service=batch.entries[0].service if batch.entries else None,
        )
        
        # In debug mode, show first log
        if batch.entries:
            logger.debug(
                "First log in batch",
                message=batch.entries[0].message[:100],
                level=batch.entries[0].level,
            )

    async def send_metrics(self, batch: MetricBatch) -> None:
        """Mock send metric batch.
        
        Args:
            batch: Metric batch to send
            
        Raises:
            ProducerError: If producer is closed
        """
        if self.is_closed:
            raise ProducerError("Producer is closed")
        
        # Convert Pydantic model to dict
        batch_dict = batch.model_dump(mode="json")
        
        # Store in memory
        self.metrics_sent.append(batch_dict)
        
        # Log the action
        logger.info(
            "Mock: Metric batch sent to Kafka",
            topic="metrics.raw",
            num_metrics=len(batch.entries),
            service=batch.entries[0].service if batch.entries else None,
        )
        
        # In debug mode, show first metric
        if batch.entries:
            logger.debug(
                "First metric in batch",
                name=batch.entries[0].name,
                value=batch.entries[0].value,
            )

    async def close(self) -> None:
        """Close the mock producer."""
        self.is_closed = True
        logger.info(
            "Mock producer closed",
            total_logs_sent=len(self.logs_sent),
            total_metrics_sent=len(self.metrics_sent),
        )

    async def flush(self) -> None:
        """Flush (no-op for mock)."""
        logger.debug("Mock producer flush (no-op)")

    def get_sent_logs(self) -> List[Dict[str, Any]]:
        """Get all logs sent (for testing).
        
        Returns:
            List of log batches sent
        """
        return self.logs_sent

    def get_sent_metrics(self) -> List[Dict[str, Any]]:
        """Get all metrics sent (for testing).
        
        Returns:
            List of metric batches sent
        """
        return self.metrics_sent

    def clear(self) -> None:
        """Clear sent messages (for testing).
        
        Useful for resetting state between tests.
        """
        self.logs_sent.clear()
        self.metrics_sent.clear()
        logger.debug("Mock producer cleared")


class KafkaProducer(BaseProducer):
    """Real Kafka producer using aiokafka.
    
    This will be implemented in Phase 3 when we add Kafka.
    For now, it's a placeholder that raises NotImplementedError.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        logs_topic: str = "logs.raw",
        metrics_topic: str = "metrics.raw",
    ):
        """Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka broker addresses (e.g., "localhost:9092")
            logs_topic: Topic for logs
            metrics_topic: Topic for metrics
        """
        self.bootstrap_servers = bootstrap_servers
        self.logs_topic = logs_topic
        self.metrics_topic = metrics_topic
        self.producer: Optional[Any] = None
        
        logger.info(
            "Kafka producer initialized (will connect in Phase 3)",
            bootstrap_servers=bootstrap_servers,
        )

    async def send_logs(self, batch: LogBatch) -> None:
        """Send log batch to Kafka.
        
        Args:
            batch: Log batch to send
            
        Raises:
            NotImplementedError: Real Kafka not implemented yet (Phase 3)
        """
        raise NotImplementedError(
            "Real Kafka producer will be implemented in Phase 3. "
            "Use MockKafkaProducer for now."
        )

    async def send_metrics(self, batch: MetricBatch) -> None:
        """Send metric batch to Kafka.
        
        Args:
            batch: Metric batch to send
            
        Raises:
            NotImplementedError: Real Kafka not implemented yet (Phase 3)
        """
        raise NotImplementedError(
            "Real Kafka producer will be implemented in Phase 3. "
            "Use MockKafkaProducer for now."
        )

    async def close(self) -> None:
        """Close the producer."""
        logger.info("Kafka producer closed")

    async def flush(self) -> None:
        """Flush pending messages."""
        logger.debug("Kafka producer flush")


class ProducerFactory:
    """Factory for creating producers.
    
    Automatically selects mock or real producer based on configuration.
    """

    @staticmethod
    def create_producer() -> BaseProducer:
        """Create a producer based on settings.
        
        Returns:
            Mock producer (for now, until Phase 3)
            
        Example:
            ```python
            producer = ProducerFactory.create_producer()
            await producer.send_logs(batch)
            ```
        """
        settings = get_settings()
        
        # For Phase 2, always use mock
        # In Phase 3, we'll check settings.kafka_enabled
        use_mock = True  # Change this in Phase 3
        
        if use_mock:
            logger.info("Using MockKafkaProducer (Kafka not enabled)")
            return MockKafkaProducer()
        else:
            # This will be enabled in Phase 3
            logger.info("Using real KafkaProducer")
            return KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                logs_topic="logs.raw",
                metrics_topic="metrics.raw",
            )


# Global producer instance
# This is created when the app starts
_producer: Optional[BaseProducer] = None


async def get_producer() -> BaseProducer:
    """Get or create the global producer instance.
    
    This is a FastAPI dependency that provides the producer to endpoints.
    
    Returns:
        The global producer instance
        
    Example:
        ```python
        @app.post("/logs")
        async def ingest_logs(
            batch: LogBatch,
            producer: BaseProducer = Depends(get_producer)
        ):
            await producer.send_logs(batch)
        ```
    """
    global _producer
    
    if _producer is None:
        _producer = ProducerFactory.create_producer()
    
    return _producer


async def close_producer() -> None:
    """Close the global producer.
    
    This should be called when the app shuts down.
    """
    global _producer
    
    if _producer is not None:
        await _producer.close()
        _producer = None
        logger.info("Global producer closed")


# Real Kafka implementation helpers (for Phase 3)
# These will be used when we implement the real KafkaProducer

async def _send_to_kafka_real(
    producer: Any,
    topic: str,
    key: Optional[str],
    value: dict,
) -> None:
    """Send a message to Kafka (real implementation for Phase 3).
    
    Args:
        producer: aiokafka AIOKafkaProducer instance
        topic: Kafka topic
        key: Optional message key
        value: Message value (will be JSON serialized)
        
    Raises:
        ProducerError: If send fails
    """
    try:
        # Serialize to JSON
        value_bytes = json.dumps(value).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        
        # Send to Kafka
        # This will be implemented in Phase 3 using aiokafka
        # await producer.send(topic, value=value_bytes, key=key_bytes)
        
        logger.debug(
            "Message sent to Kafka",
            topic=topic,
            key=key,
            size_bytes=len(value_bytes),
        )
        
    except Exception as e:
        logger.error(
            "Failed to send message to Kafka",
            topic=topic,
            error=str(e),
        )
        raise ProducerError(f"Kafka send failed: {e}")


def _create_message_key(service: str, host: str) -> str:
    """Create a Kafka message key for partitioning.
    
    Messages with the same key go to the same partition,
    preserving order for logs/metrics from the same source.
    
    Args:
        service: Service name
        host: Host name
        
    Returns:
        Message key (e.g., "api-server:web-01")
    """
    return f"{service}:{host}"


# Example of how real Kafka producer will work in Phase 3:
"""
from aiokafka import AIOKafkaProducer

class KafkaProducer(BaseProducer):
    async def connect(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        )
        await self.producer.start()
    
    async def send_logs(self, batch: LogBatch):
        for log in batch.entries:
            key = _create_message_key(log.service, log.host)
            await self.producer.send(
                self.logs_topic,
                key=key.encode('utf-8'),
                value=log.model_dump(mode='json'),
            )
        await self.producer.flush()
"""