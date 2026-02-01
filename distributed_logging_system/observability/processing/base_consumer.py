"""Base consumer class for Kafka consumers.

This module provides an abstract base class for building Kafka consumers
with common functionality like connection management, error handling,
and graceful shutdown.
"""
import asyncio
import signal
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from observability.common.config import get_settings
from observability.common.logger import get_logger

logger = get_logger(__name__)


class BaseConsumer(ABC):
    """Abstract base class for Kafka consumers.
    
    Provides common functionality:
    - Connection management
    - Message consumption loop
    - Error handling and retries
    - Graceful shutdown
    - Offset management
    
    Subclasses must implement:
    - process_message() - How to process each message
    - get_topics() - Which topics to consume from
    
    Example:
        ```python
        class LogProcessor(BaseConsumer):
            def get_topics(self) -> List[str]:
                return ["logs.raw"]
            
            async def process_message(self, message: Dict[str, Any]) -> None:
                log = message["value"]
                # Process log...
        
        processor = LogProcessor()
        await processor.start()
        ```
    """
    
    def __init__(
        self,
        consumer_group: str,
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
    ):
        """Initialize base consumer.
        
        Args:
            consumer_group: Consumer group ID (e.g., "log-processors")
            bootstrap_servers: Kafka broker addresses (default: from config)
            auto_offset_reset: Where to start reading (earliest/latest)
            enable_auto_commit: Auto-commit offsets after processing
        """
        self.consumer_group = consumer_group
        self.bootstrap_servers = bootstrap_servers or get_settings().kafka_bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self.messages_processed = 0
        self.messages_failed = 0
        
        logger.info(
            "Consumer initialized",
            consumer_group=consumer_group,
            bootstrap_servers=self.bootstrap_servers,
        )
    
    @abstractmethod
    def get_topics(self) -> List[str]:
        """Get list of topics to consume from.
        
        Returns:
            List of topic names
            
        Example:
            return ["logs.raw", "logs.processed"]
        """
        pass
    
    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> None:
        """Process a single message.
        
        Args:
            message: Message dict with keys:
                - topic: Topic name
                - partition: Partition number
                - offset: Message offset
                - key: Message key (bytes or None)
                - value: Message value (parsed from JSON)
                - timestamp: Message timestamp
        
        Raises:
            Exception: If processing fails (will be logged and counted)
        """
        pass
    
    async def _create_consumer(self) -> AIOKafkaConsumer:
        """Create and start Kafka consumer.
        
        Returns:
            Started AIOKafkaConsumer instance
        """
        import json
        
        topics = self.get_topics()
        
        logger.info(
            "Creating Kafka consumer",
            topics=topics,
            consumer_group=self.consumer_group,
        )
        
        consumer = AIOKafkaConsumer(
            *topics,  # Unpack topic list
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=self.enable_auto_commit,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
        )
        
        await consumer.start()
        
        logger.info(
            "Kafka consumer started",
            topics=topics,
            partitions=consumer.assignment(),
        )
        
        return consumer
    
    async def start(self) -> None:
        """Start consuming messages.
        
        This method runs indefinitely until stopped via Ctrl+C or stop().
        It handles:
        - Consumer creation and connection
        - Message consumption loop
        - Error handling and retries
        - Graceful shutdown
        """
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        def signal_handler():
            logger.info("Shutdown signal received")
            self._shutdown_event.set()
        
        # Register Ctrl+C handler
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
        
        try:
            # Create consumer
            self.consumer = await self._create_consumer()
            
            logger.info(
                "Consumer started, waiting for messages...",
                consumer_group=self.consumer_group,
            )
            
            # Main consumption loop
            async for message in self.consumer:
                # Check for shutdown
                if self._shutdown_event.is_set():
                    break
                
                try:
                    # Parse message
                    parsed_message = {
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "key": message.key,
                        "value": message.value,
                        "timestamp": message.timestamp,
                    }
                    
                    logger.debug(
                        "Processing message",
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                        key=message.key,
                    )
                    
                    # Process message (subclass implementation)
                    await self.process_message(parsed_message)
                    
                    self.messages_processed += 1
                    
                    if self.messages_processed % 100 == 0:
                        logger.info(
                            "Processing progress",
                            messages_processed=self.messages_processed,
                            messages_failed=self.messages_failed,
                        )
                
                except Exception as e:
                    self.messages_failed += 1
                    
                    logger.error(
                        "Failed to process message",
                        error=str(e),
                        error_type=type(e).__name__,
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                    )
                    
                    # Continue processing (don't crash on single message failure)
                    continue
        
        except KafkaError as e:
            logger.error(
                "Kafka error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the consumer gracefully.
        
        Commits offsets and closes the consumer.
        """
        if not self.running:
            return
        
        self.running = False
        
        logger.info(
            "Stopping consumer",
            messages_processed=self.messages_processed,
            messages_failed=self.messages_failed,
        )
        
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Consumer stopped")
            except Exception as e:
                logger.error(
                    "Error stopping consumer",
                    error=str(e),
                    error_type=type(e).__name__,
                )
    
    def get_statistics(self) -> Dict[str, int]:
        """Get consumer statistics.
        
        Returns:
            Dict with processing statistics
        """
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "success_rate": (
                self.messages_processed / (self.messages_processed + self.messages_failed)
                if (self.messages_processed + self.messages_failed) > 0
                else 0.0
            ),
        }