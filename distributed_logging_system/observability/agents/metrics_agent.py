"""Metrics collection agent.

This agent collects system metrics (CPU, memory, disk) and application-level
metrics, then sends them to the ingestion API with batching and retry logic.
"""
import asyncio
import os
import signal
from datetime import datetime
from typing import List, Optional

import httpx
import psutil

from observability.common.config import get_settings
from observability.common.logger import get_logger
from observability.common.models import MetricBatch, MetricEntry, MetricType
from observability.common.retry import RetryConfig, retry_async

logger = get_logger(__name__)


class MetricsAgent:
    """Agent that collects and sends system metrics to the ingestion service.
    
    Collects:
    - CPU usage (overall and per-core)
    - Memory usage (total, available, percent)
    - Disk usage (total, used, free)
    - Network I/O (bytes sent/received)
    - Process-specific metrics (optional)
    
    Example:
        ```python
        agent = MetricsAgent(
            service_name="api-server",
            collection_interval=10.0  # Collect every 10 seconds
        )
        await agent.start()
        ```
    """

    def __init__(
        self,
        service_name: str,
        environment: Optional[str] = None,
        ingestion_url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_interval: float = 10.0,
        batch_size: int = 50,
        buffer_size: int = 1000,
        collect_per_cpu: bool = False,
        collect_disk: bool = True,
        collect_network: bool = True,
    ):
        """Initialize the metrics agent.
        
        Args:
            service_name: Name of the service
            environment: Environment (dev/staging/prod)
            ingestion_url: URL of ingestion API
            api_key: API key for authentication
            collection_interval: Seconds between metric collections
            batch_size: Number of metrics to batch before sending
            buffer_size: Maximum metrics to buffer in memory
            collect_per_cpu: Collect per-CPU core metrics (can be verbose)
            collect_disk: Collect disk usage metrics
            collect_network: Collect network I/O metrics
        """
        settings = get_settings()
        
        self.service_name = service_name
        self.environment = environment or settings.environment
        self.hostname = os.getenv("HOSTNAME", os.uname().nodename)
        
        # API configuration
        self.ingestion_url = ingestion_url or (
            f"http://{settings.ingestion_host}:{settings.ingestion_port}/metrics"
        )
        self.api_key = api_key or settings.ingestion_api_key
        
        # Collection configuration
        self.collection_interval = collection_interval
        self.batch_size = batch_size
        self.buffer_size = buffer_size
        self.collect_per_cpu = collect_per_cpu
        self.collect_disk = collect_disk
        self.collect_network = collect_network
        
        # Internal state
        self.buffer: List[MetricEntry] = []
        self.http_client: Optional[httpx.AsyncClient] = None
        self.running = False
        self.retry_config = RetryConfig(
            max_retries=settings.max_retries,
            initial_delay=1.0,
            max_delay=30.0,
        )
        
        # For calculating rates (network bytes per second)
        self.last_network_counters: Optional[dict] = None
        self.last_collection_time: Optional[datetime] = None
        
        logger.info(
            "Metrics agent initialized",
            service=service_name,
            environment=self.environment,
            collection_interval=collection_interval,
            ingestion_url=self.ingestion_url,
        )

    async def start(self) -> None:
        """Start the metrics agent.
        
        This will:
        1. Start collecting metrics periodically
        2. Start the batch flusher
        3. Handle graceful shutdown on SIGTERM/SIGINT
        """
        self.running = True
        
        # Setup HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers={"X-API-Key": self.api_key},
        )
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )
        
        logger.info("Metrics agent started")
        
        try:
            # Run collector and flusher concurrently
            await asyncio.gather(
                self._collect_metrics_periodically(),
                self._flush_periodically(),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent."""
        if not self.running:
            return
        
        logger.info("Shutting down metrics agent")
        self.running = False
        
        # Flush remaining metrics
        if self.buffer:
            await self._flush()
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Metrics agent stopped")

    async def _collect_metrics_periodically(self) -> None:
        """Collect metrics at regular intervals."""
        while self.running:
            try:
                await self._collect_metrics()
            except Exception as e:
                logger.error("Error collecting metrics", error=str(e))
            
            # Wait before next collection
            await asyncio.sleep(self.collection_interval)

    async def _collect_metrics(self) -> None:
        """Collect all configured metrics.
        
        This is where the actual metric collection happens using psutil.
        """
        timestamp = datetime.utcnow()
        
        # Collect CPU metrics
        await self._collect_cpu_metrics(timestamp)
        
        # Collect memory metrics
        await self._collect_memory_metrics(timestamp)
        
        # Collect disk metrics (if enabled)
        if self.collect_disk:
            await self._collect_disk_metrics(timestamp)
        
        # Collect network metrics (if enabled)
        if self.collect_network:
            await self._collect_network_metrics(timestamp)
        
        logger.debug("Metrics collected", buffer_size=len(self.buffer))

    async def _collect_cpu_metrics(self, timestamp: datetime) -> None:
        """Collect CPU usage metrics.
        
        Args:
            timestamp: When metrics were collected
        """
        # Overall CPU usage percentage
        # interval=1.0 means measure over 1 second for accuracy
        cpu_percent = psutil.cpu_percent(interval=1.0)
        
        await self._add_metric(
            name="system.cpu.usage_percent",
            value=cpu_percent,
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="percent",
            labels={"cpu": "total"},
        )
        
        # Per-CPU core metrics (if enabled)
        if self.collect_per_cpu:
            per_cpu_percent = psutil.cpu_percent(interval=1.0, percpu=True)
            
            for cpu_num, percent in enumerate(per_cpu_percent):
                await self._add_metric(
                    name="system.cpu.usage_percent",
                    value=percent,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="percent",
                    labels={"cpu": f"cpu{cpu_num}"},
                )
        
        # CPU count
        cpu_count = psutil.cpu_count(logical=True)
        await self._add_metric(
            name="system.cpu.count",
            value=float(cpu_count),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="count",
        )
        
        # Load average (Unix-like systems only)
        try:
            load1, load5, load15 = psutil.getloadavg()
            
            await self._add_metric(
                name="system.cpu.load_average",
                value=load1,
                timestamp=timestamp,
                metric_type=MetricType.GAUGE,
                labels={"period": "1min"},
            )
            
            await self._add_metric(
                name="system.cpu.load_average",
                value=load5,
                timestamp=timestamp,
                metric_type=MetricType.GAUGE,
                labels={"period": "5min"},
            )
            
            await self._add_metric(
                name="system.cpu.load_average",
                value=load15,
                timestamp=timestamp,
                metric_type=MetricType.GAUGE,
                labels={"period": "15min"},
            )
        except AttributeError:
            # getloadavg() not available on Windows
            pass

    async def _collect_memory_metrics(self, timestamp: datetime) -> None:
        """Collect memory usage metrics.
        
        Args:
            timestamp: When metrics were collected
        """
        # Virtual memory (RAM)
        mem = psutil.virtual_memory()
        
        await self._add_metric(
            name="system.memory.total_bytes",
            value=float(mem.total),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.memory.available_bytes",
            value=float(mem.available),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.memory.used_bytes",
            value=float(mem.used),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.memory.usage_percent",
            value=mem.percent,
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="percent",
        )
        
        # Swap memory
        swap = psutil.swap_memory()
        
        await self._add_metric(
            name="system.swap.total_bytes",
            value=float(swap.total),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.swap.used_bytes",
            value=float(swap.used),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.swap.usage_percent",
            value=swap.percent,
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            unit="percent",
        )

    async def _collect_disk_metrics(self, timestamp: datetime) -> None:
        """Collect disk usage metrics.
        
        Args:
            timestamp: When metrics were collected
        """
        # Get all disk partitions
        partitions = psutil.disk_partitions()
        
        for partition in partitions:
            # Skip special filesystems (proc, sys, etc.)
            if partition.fstype == "" or "loop" in partition.device:
                continue
            
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                # Use mountpoint as label
                mount = partition.mountpoint
                
                await self._add_metric(
                    name="system.disk.total_bytes",
                    value=float(usage.total),
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="bytes",
                    labels={"mountpoint": mount},
                )
                
                await self._add_metric(
                    name="system.disk.used_bytes",
                    value=float(usage.used),
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="bytes",
                    labels={"mountpoint": mount},
                )
                
                await self._add_metric(
                    name="system.disk.free_bytes",
                    value=float(usage.free),
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="bytes",
                    labels={"mountpoint": mount},
                )
                
                await self._add_metric(
                    name="system.disk.usage_percent",
                    value=usage.percent,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="percent",
                    labels={"mountpoint": mount},
                )
                
            except PermissionError:
                # Can't access some mountpoints without root
                continue

    async def _collect_network_metrics(self, timestamp: datetime) -> None:
        """Collect network I/O metrics.
        
        Args:
            timestamp: When metrics were collected
        """
        # Get network I/O counters
        net_io = psutil.net_io_counters()
        
        # Total bytes sent/received (cumulative counters)
        await self._add_metric(
            name="system.network.bytes_sent",
            value=float(net_io.bytes_sent),
            timestamp=timestamp,
            metric_type=MetricType.COUNTER,
            unit="bytes",
        )
        
        await self._add_metric(
            name="system.network.bytes_received",
            value=float(net_io.bytes_recv),
            timestamp=timestamp,
            metric_type=MetricType.COUNTER,
            unit="bytes",
        )
        
        # Calculate rate (bytes per second) if we have previous data
        if self.last_network_counters and self.last_collection_time:
            time_delta = (timestamp - self.last_collection_time).total_seconds()
            
            if time_delta > 0:
                bytes_sent_rate = (
                    net_io.bytes_sent - self.last_network_counters["bytes_sent"]
                ) / time_delta
                
                bytes_recv_rate = (
                    net_io.bytes_recv - self.last_network_counters["bytes_recv"]
                ) / time_delta
                
                await self._add_metric(
                    name="system.network.bytes_sent_per_second",
                    value=bytes_sent_rate,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="bytes_per_second",
                )
                
                await self._add_metric(
                    name="system.network.bytes_received_per_second",
                    value=bytes_recv_rate,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    unit="bytes_per_second",
                )
        
        # Save for next iteration
        self.last_network_counters = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
        }
        self.last_collection_time = timestamp

    async def _add_metric(
        self,
        name: str,
        value: float,
        timestamp: datetime,
        metric_type: MetricType,
        unit: Optional[str] = None,
        labels: Optional[dict] = None,
    ) -> None:
        """Add a metric to the buffer.
        
        Args:
            name: Metric name
            value: Metric value
            timestamp: When metric was collected
            metric_type: Type of metric (counter/gauge/histogram)
            unit: Unit of measurement
            labels: Additional labels/dimensions
        """
        # Check buffer size limit
        if len(self.buffer) >= self.buffer_size:
            logger.warning(
                "Buffer full, dropping oldest metric",
                buffer_size=self.buffer_size,
            )
            self.buffer.pop(0)
        
        # Create metric entry
        entry = MetricEntry(
            timestamp=timestamp,
            name=name,
            value=value,
            metric_type=metric_type,
            service=self.service_name,
            environment=self.environment,
            host=self.hostname,
            labels=labels or {},
            unit=unit,
        )
        
        self.buffer.append(entry)
        
        # Flush if batch size reached
        if len(self.buffer) >= self.batch_size:
            await self._flush()

    async def _flush_periodically(self) -> None:
        """Flush metrics on a timer.
        
        For metrics, we flush less frequently than logs since we collect
        in batches already. Default is after each collection cycle.
        """
        while self.running:
            # Wait for 2x collection interval before flushing
            # This allows batching multiple collection cycles
            await asyncio.sleep(self.collection_interval * 2)
            
            if self.buffer:
                await self._flush()

    async def _flush(self) -> None:
        """Send buffered metrics to ingestion API."""
        if not self.buffer:
            return
        
        # Take all metrics from buffer
        metrics_to_send = self.buffer.copy()
        self.buffer.clear()
        
        try:
            # Create batch
            batch = MetricBatch(entries=metrics_to_send)
            
            logger.debug(
                "Sending metrics batch",
                count=len(metrics_to_send),
                url=self.ingestion_url,
            )
            
            # Send with retry
            await retry_async(
                self._send_batch,
                batch,
                config=self.retry_config,
                retry_on_exceptions=(httpx.HTTPError, httpx.TimeoutException),
            )
            
            logger.debug("Metrics batch sent successfully", count=len(metrics_to_send))
            
        except Exception as e:
            logger.error(
                "Failed to send metrics after retries",
                count=len(metrics_to_send),
                error=str(e),
            )

    async def _send_batch(self, batch: MetricBatch) -> None:
        """Send a batch to the ingestion API.
        
        Args:
            batch: Batch of metric entries
            
        Raises:
            httpx.HTTPError: On HTTP errors
            httpx.TimeoutException: On timeout
        """
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")
        
        response = await self.http_client.post(
            self.ingestion_url,
            json=batch.model_dump(mode="json"),
        )
        
        response.raise_for_status()


async def main() -> None:
    """Main entry point for the metrics agent.
    
    Usage:
        python -m observability.agents.metrics_agent --service my-app
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Metrics collection agent")
    parser.add_argument(
        "--service",
        required=True,
        help="Service name",
    )
    parser.add_argument(
        "--environment",
        help="Environment (dev/staging/prod)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Collection interval in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size (default: 50)",
    )
    parser.add_argument(
        "--per-cpu",
        action="store_true",
        help="Collect per-CPU core metrics",
    )
    parser.add_argument(
        "--no-disk",
        action="store_true",
        help="Disable disk metrics collection",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Disable network metrics collection",
    )
    
    args = parser.parse_args()
    
    # Create and start agent
    agent = MetricsAgent(
        service_name=args.service,
        environment=args.environment,
        collection_interval=args.interval,
        batch_size=args.batch_size,
        collect_per_cpu=args.per_cpu,
        collect_disk=not args.no_disk,
        collect_network=not args.no_network,
    )
    
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())