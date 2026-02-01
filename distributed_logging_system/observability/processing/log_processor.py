"""Log processor - consumes and processes logs from Kafka.

This processor:
1. Reads log batches from logs.raw topic
2. Parses and enriches each log entry
3. Prints to console (Phase 4) / Saves to database (Phase 5)
"""
import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from observability.common.logger import get_logger
from observability.processing.base_consumer import BaseConsumer
from observability.storage import OpenSearchWriter

logger = get_logger(__name__)


class LogProcessor(BaseConsumer):
    """Processes logs from Kafka.
    
    Consumes from: logs.raw
    Processes: Individual log entries
    Output: Console logs (Phase 4), Database (Phase 5)
    
    Example:
        ```python
        processor = LogProcessor()
        await processor.start()  # Runs until Ctrl+C
        ```
    """
    
    def __init__(self, consumer_group: str = "log-processors"):
        """Initialize log processor.
        
        Args:
            consumer_group: Consumer group ID (default: "log-processors")
        """
        super().__init__(
            consumer_group=consumer_group,
            auto_offset_reset="earliest",  # Process from beginning
            enable_auto_commit=True,  # Auto-commit after processing
        )
        
        # Statistics
        self.logs_by_level = {
            "DEBUG": 0,
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "CRITICAL": 0,
        }
        
         # OpenSearch writer (lazy init)
        self.opensearch_writer = None
        self.opensearch_enabled = os.getenv("OPENSEARCH_ENABLED", "true").lower() == "true"
        
        logger.info(
            "Log processor initialized",
            consumer_group=consumer_group,
            opensearch_enabled=self.opensearch_enabled,
        )
        
    async def start(self) -> None:
        """Start processor and connect to OpenSearch."""
        # Connect to OpenSearch FIRST
        if self.opensearch_writer:
            await self.opensearch_writer.connect()
        
        # Then start consumer
        await super().start()  # ← Calls BaseConsumer.start()
        
    async def shutdown(self) -> None:
        """Shutdown processor and close OpenSearch."""
        # Shutdown consumer FIRST
        await super().shutdown()  # ← Calls BaseConsumer.shutdown()
        
        # Then close OpenSearch
        if self.opensearch_writer:
            await self.opensearch_writer.close()    
    
    async def _ensure_opensearch_connected(self) -> None:
        """Ensure OpenSearch writer is connected (lazy initialization)."""
        if not self.opensearch_enabled:
            return
        
        if self.opensearch_writer is None:
            from observability.storage import OpenSearchWriter
            
            self.opensearch_writer = OpenSearchWriter(
                hosts=[os.getenv("OPENSEARCH_HOSTS", "http://localhost:9200")],
                batch_size=int(os.getenv("OPENSEARCH_BATCH_SIZE", "100")),
            )
            
            await self.opensearch_writer.connect()
            logger.info("OpenSearch writer connected")
    
    def get_topics(self) -> List[str]:
        """Get topics to consume from.
        
        Returns:
            List containing "logs.raw"
        """
        return ["logs.raw"]
    
    async def process_message(self, message: Dict[str, Any]) -> None:
        """Process a log message from Kafka.
        
        Args:
            message: Message dict with:
                - value: {"entries": [...], "agent_version": "0.1.0"}
                - key: "service:host"
                - partition: Partition number
                - offset: Message offset
        """
        
        await self._ensure_opensearch_connected()

        # Extract batch data
        batch = message["value"]
        entries = batch.get("entries", [])
        agent_version = batch.get("agent_version", "unknown")
        
        logger.debug(
            "Processing log batch",
            num_logs=len(entries),
            partition=message["partition"],
            offset=message["offset"],
            key=message["key"],
        )
        
        # Process each log entry
        for entry in entries:
            await self._process_log_entry(entry, agent_version)
    
    async def _process_log_entry(self, entry: Dict[str, Any], agent_version: str) -> None:
        """Process a single log entry.
        
        Args:
            entry: Log entry dict
            agent_version: Version of agent that sent this log
        """
        # Parse log fields
        timestamp_str = entry.get("timestamp", "")
        level = entry.get("level", "INFO").upper()
        message = entry.get("message", "")
        service = entry.get("service", "unknown")
        host = entry.get("host", "unknown")
        environment = entry.get("environment", "development")
        labels = entry.get("labels", {})
        trace_id = entry.get("trace_id")
        span_id = entry.get("span_id")
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()
        
        # Update statistics
        if level in self.logs_by_level:
            self.logs_by_level[level] += 1
        
        # Enrich log (add processing metadata)
        enriched_log = {
            "timestamp": timestamp.isoformat(),
            "level": level,
            "message": message,
            "service": service,
            "host": host,
            "environment": environment,
            "labels": labels,
            "trace_id": trace_id,
            "span_id": span_id,
            "agent_version": agent_version,
            "processed_at": datetime.utcnow().isoformat(),
            "processor": "log-processor",
        }
        
        # Phase 4: Print to console
        # Phase 5: Save to database
        self._output_log(enriched_log)
        
        if self.opensearch_writer:
            await self.opensearch_writer.write(enriched_log)
    
    def _output_log(self, log: Dict[str, Any]) -> None:
        """Output processed log.
        
        Phase 4: Print to console
        Phase 5: Save to database
        
        Args:
            log: Enriched log entry
        """
        # Format log message for console
        level = log["level"]
        timestamp = log["timestamp"]
        service = log["service"]
        host = log["host"]
        message = log["message"]
        
        # Color codes for different log levels
        colors = {
            "DEBUG": "\033[36m",     # Cyan
            "INFO": "\033[32m",      # Green
            "WARNING": "\033[33m",   # Yellow
            "ERROR": "\033[31m",     # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        reset = "\033[0m"
        
        color = colors.get(level, "")
        
        # Print formatted log
        print(
            f"{color}[{level:8s}]{reset} "
            f"{timestamp} "
            f"| {service:15s} "
            f"| {host:15s} "
            f"| {message}"
        )
        
        # If trace_id exists, show it
        if log.get("trace_id"):
            print(f"  └─ trace_id={log['trace_id']}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processor statistics.
        
        Returns:
            Dict with processing stats and log level counts
        """
        base_stats = super().get_statistics()
        
        return {
            **base_stats,
            "logs_by_level": self.logs_by_level,
            "total_logs": sum(self.logs_by_level.values()),
        }


async def main():
    """Main entry point for running log processor standalone."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Log processor")
    parser.add_argument(
        "--consumer-group",
        default="log-processors",
        help="Consumer group ID (default: log-processors)",
    )
    
    args = parser.parse_args()
    
    # Create and start processor
    processor = LogProcessor(consumer_group=args.consumer_group)
    
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Print final statistics
        stats = processor.get_statistics()
        logger.info("Final statistics", **stats)


if __name__ == "__main__":
    asyncio.run(main())