"""Metrics processor - consumes and aggregates metrics from Kafka.

This processor:
1. Reads metric batches from metrics.raw topic
2. Aggregates metrics (avg, min, max, sum, count)
3. Prints statistics to console (Phase 4) / Saves to DB (Phase 5)
"""
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from observability.common.logger import get_logger
from observability.processing.base_consumer import BaseConsumer

logger = get_logger(__name__)


class MetricsAggregator:
    """Aggregates metrics over time windows.
    
    Tracks: min, max, sum, count, avg for each metric.
    """
    
    def __init__(self):
        """Initialize aggregator."""
        self.metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "sum": 0.0,
                "min": float('inf'),
                "max": float('-inf'),
                "last_value": 0.0,
                "last_timestamp": None,
            }
        )
    
    def add_metric(self, name: str, value: float, timestamp: str) -> None:
        """Add a metric value.
        
        Args:
            name: Metric name (e.g., "cpu_percent")
            value: Metric value
            timestamp: When metric was collected
        """
        m = self.metrics[name]
        
        m["count"] += 1
        m["sum"] += value
        m["min"] = min(m["min"], value)
        m["max"] = max(m["max"], value)
        m["last_value"] = value
        m["last_timestamp"] = timestamp
    
    def get_aggregates(self, name: str) -> Dict[str, Any]:
        """Get aggregated statistics for a metric.
        
        Args:
            name: Metric name
            
        Returns:
            Dict with min, max, avg, sum, count
        """
        if name not in self.metrics:
            return {}
        
        m = self.metrics[name]
        
        return {
            "count": m["count"],
            "sum": m["sum"],
            "min": m["min"],
            "max": m["max"],
            "avg": m["sum"] / m["count"] if m["count"] > 0 else 0.0,
            "last_value": m["last_value"],
            "last_timestamp": m["last_timestamp"],
        }
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all aggregated metrics.
        
        Returns:
            Dict mapping metric name to aggregates
        """
        return {
            name: self.get_aggregates(name)
            for name in self.metrics.keys()
        }
    
    def reset(self) -> None:
        """Reset all aggregations."""
        self.metrics.clear()


class MetricsProcessor(BaseConsumer):
    """Processes metrics from Kafka.
    
    Consumes from: metrics.raw
    Processes: Metric batches, aggregates values
    Output: Console statistics (Phase 4), Database (Phase 5)
    
    Example:
        ```python
        processor = MetricsProcessor()
        await processor.start()  # Runs until Ctrl+C
        ```
    """
    
    def __init__(self, consumer_group: str = "metrics-processors"):
        """Initialize metrics processor.
        
        Args:
            consumer_group: Consumer group ID (default: "metrics-processors")
        """
        super().__init__(
            consumer_group=consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        
        # Aggregators per service
        self.aggregators: Dict[str, MetricsAggregator] = defaultdict(MetricsAggregator)
        
        # Statistics
        self.metrics_by_type = {
            "counter": 0,
            "gauge": 0,
            "histogram": 0,
        }
        
        # Print statistics every N messages
        self.print_interval = 10
        self.messages_since_print = 0
        
        logger.info("Metrics processor initialized")
    
    def get_topics(self) -> List[str]:
        """Get topics to consume from.
        
        Returns:
            List containing "metrics.raw"
        """
        return ["metrics.raw"]
    
    async def process_message(self, message: Dict[str, Any]) -> None:
        """Process a metric message from Kafka.
        
        Args:
            message: Message dict with:
                - value: {"entries": [...], "agent_version": "0.1.0"}
                - key: "service:host"
        """
        # Extract batch data
        batch = message["value"]
        entries = batch.get("entries", [])
        agent_version = batch.get("agent_version", "unknown")
        
        logger.debug(
            "Processing metric batch",
            num_metrics=len(entries),
            partition=message["partition"],
            offset=message["offset"],
            key=message["key"],
        )
        
        # Process each metric entry
        for entry in entries:
            await self._process_metric_entry(entry, agent_version)
        
        # Print statistics periodically
        self.messages_since_print += 1
        if self.messages_since_print >= self.print_interval:
            self._print_statistics()
            self.messages_since_print = 0
    
    async def _process_metric_entry(self, entry: Dict[str, Any], agent_version: str) -> None:
        """Process a single metric entry.
        
        Args:
            entry: Metric entry dict
            agent_version: Version of agent that sent this metric
        """
        # Parse metric fields
        timestamp_str = entry.get("timestamp", "")
        name = entry.get("name", "unknown")
        value = entry.get("value", 0.0)
        metric_type = entry.get("metric_type", "gauge")
        service = entry.get("service", "unknown")
        host = entry.get("host", "unknown")
        environment = entry.get("environment", "development")
        labels = entry.get("labels", {})
        unit = entry.get("unit")
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()
        
        # Update type statistics
        if metric_type in self.metrics_by_type:
            self.metrics_by_type[metric_type] += 1
        
        # Add to aggregator (per service)
        aggregator = self.aggregators[service]
        aggregator.add_metric(name, value, timestamp.isoformat())
        
        # Enrich metric
        enriched_metric = {
            "timestamp": timestamp.isoformat(),
            "name": name,
            "value": value,
            "metric_type": metric_type,
            "service": service,
            "host": host,
            "environment": environment,
            "labels": labels,
            "unit": unit,
            "agent_version": agent_version,
            "processed_at": datetime.utcnow().isoformat(),
            "processor": "metrics-processor",
        }
        
        # Phase 4: Just aggregate (print later)
        # Phase 5: Save to time-series database
    
    def _print_statistics(self) -> None:
        """Print current aggregated statistics."""
        print("\n" + "=" * 80)
        print("METRICS STATISTICS")
        print("=" * 80)
        
        # Print per-service aggregates
        for service, aggregator in self.aggregators.items():
            print(f"\nService: {service}")
            print("-" * 80)
            
            metrics = aggregator.get_all_metrics()
            
            if not metrics:
                print("  No metrics yet")
                continue
            
            # Print each metric's aggregates
            for name, stats in sorted(metrics.items()):
                print(
                    f"  {name:30s} | "
                    f"avg: {stats['avg']:8.2f} | "
                    f"min: {stats['min']:8.2f} | "
                    f"max: {stats['max']:8.2f} | "
                    f"count: {stats['count']:4d}"
                )
        
        # Print overall statistics
        print("\n" + "-" * 80)
        print(f"Total messages processed: {self.messages_processed}")
        print(f"Total messages failed: {self.messages_failed}")
        print(f"Metrics by type: {self.metrics_by_type}")
        print("=" * 80 + "\n")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processor statistics.
        
        Returns:
            Dict with processing stats and aggregated metrics
        """
        base_stats = super().get_statistics()
        
        # Get all service aggregates
        service_aggregates = {
            service: aggregator.get_all_metrics()
            for service, aggregator in self.aggregators.items()
        }
        
        return {
            **base_stats,
            "metrics_by_type": self.metrics_by_type,
            "total_metrics": sum(self.metrics_by_type.values()),
            "services": list(self.aggregators.keys()),
            "service_aggregates": service_aggregates,
        }


async def main():
    """Main entry point for running metrics processor standalone."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Metrics processor")
    parser.add_argument(
        "--consumer-group",
        default="metrics-processors",
        help="Consumer group ID (default: metrics-processors)",
    )
    
    args = parser.parse_args()
    
    # Create and start processor
    processor = MetricsProcessor(consumer_group=args.consumer_group)
    
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Print final statistics
        processor._print_statistics()
        stats = processor.get_statistics()
        logger.info("Final statistics", **stats)


if __name__ == "__main__":
    asyncio.run(main())