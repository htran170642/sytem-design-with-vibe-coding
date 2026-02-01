"""OpenSearch writer for log storage.

This module provides functionality to write logs to OpenSearch indices
with batch processing, error handling, and retry logic.
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from opensearchpy import OpenSearch
from opensearchpy.exceptions import OpenSearchException
from opensearchpy.helpers import bulk

from observability.common.logger import get_logger

logger = get_logger(__name__)


class OpenSearchWriter:
    """Writes logs to OpenSearch with batch processing and error handling.
    
    Features:
    - Time-based indices (logs-YYYY-MM-DD)
    - Batch writes for efficiency
    - Automatic retry on failures
    - Connection pooling
    - Health checking
    
    Example:
        ```python
        writer = OpenSearchWriter(hosts=["http://localhost:9200"])
        await writer.connect()
        
        logs = [
            {"timestamp": "2026-01-18T...", "message": "Log 1", ...},
            {"timestamp": "2026-01-18T...", "message": "Log 2", ...},
        ]
        
        await writer.write_batch(logs)
        await writer.close()
        ```
    """
    
    def __init__(
        self,
        hosts: List[str] = None,
        index_prefix: str = "logs",
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_retries: int = 3,
    ):
        """Initialize OpenSearch writer.
        
        Args:
            hosts: List of OpenSearch hosts (e.g., ["http://localhost:9200"])
            index_prefix: Prefix for index names (default: "logs")
            batch_size: Maximum batch size for writes
            flush_interval: Seconds to wait before flushing partial batch
            max_retries: Maximum number of retry attempts
        """
        self.hosts = hosts or ["http://localhost:9200"]
        self.index_prefix = index_prefix
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        
        self.client: Optional[OpenSearch] = None
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_lock = asyncio.Lock()
        self.flush_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Statistics
        self.logs_written = 0
        self.batches_written = 0
        self.write_failures = 0
        
        logger.info(
            "OpenSearch writer initialized",
            hosts=self.hosts,
            index_prefix=self.index_prefix,
            batch_size=self.batch_size,
        )
    
    async def connect(self) -> None:
        """Connect to OpenSearch cluster.
        
        Raises:
            OpenSearchException: If connection fails
        """
        try:
            # Use synchronous client (opensearch-py doesn't have AsyncOpenSearch yet)
            self.client = OpenSearch(
                hosts=self.hosts,
                http_compress=True,
                use_ssl=False,
                verify_certs=False,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
                timeout=30,
                max_retries=self.max_retries,
                retry_on_timeout=True,
            )
            
            # Test connection (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self.client.info)
            
            logger.info(
                "Connected to OpenSearch",
                cluster_name=info.get("cluster_name"),
                version=info.get("version", {}).get("number"),
            )
            
            # Start flush timer
            self.running = True
            self.flush_task = asyncio.create_task(self._flush_periodically())
            
        except Exception as e:
            logger.error(
                "Failed to connect to OpenSearch",
                error=str(e),
                error_type=type(e).__name__,
                hosts=self.hosts,
            )
            raise
    
    async def close(self) -> None:
        """Close OpenSearch connection and flush remaining logs."""
        logger.info("Closing OpenSearch writer")
        self.running = False
        
        # Cancel flush task
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining logs
        if self.buffer:
            await self._flush()
        
        # Close client (run in executor)
        if self.client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.close)
        
        logger.info(
            "OpenSearch writer closed",
            logs_written=self.logs_written,
            batches_written=self.batches_written,
            write_failures=self.write_failures,
        )
    
    async def write(self, log: Dict[str, Any]) -> None:
        """Write a single log entry.
        
        Args:
            log: Log entry dictionary
        """
        await self.write_batch([log])
    
    async def write_batch(self, logs: List[Dict[str, Any]]) -> None:
        """Write a batch of log entries.
        
        Logs are buffered and written in batches for efficiency.
        
        Args:
            logs: List of log entry dictionaries
        """
        async with self.buffer_lock:
            self.buffer.extend(logs)
            
            # Flush if buffer is full
            if len(self.buffer) >= self.batch_size:
                await self._flush()
    
    async def _flush(self) -> None:
        """Flush buffered logs to OpenSearch.
        
        This is called automatically when buffer is full or on timer.
        """
        if not self.buffer:
            return
        
        async with self.buffer_lock:
            logs_to_write = self.buffer.copy()
            self.buffer.clear()
        
        try:
            await self._write_to_opensearch(logs_to_write)
            
            self.logs_written += len(logs_to_write)
            self.batches_written += 1
            
            logger.debug(
                "Batch written to OpenSearch",
                count=len(logs_to_write),
                total_logs=self.logs_written,
                total_batches=self.batches_written,
            )
            
        except Exception as e:
            self.write_failures += 1
            logger.error(
                "Failed to write batch to OpenSearch",
                error=str(e),
                error_type=type(e).__name__,
                count=len(logs_to_write),
            )
            
            # Put logs back in buffer for retry
            async with self.buffer_lock:
                self.buffer = logs_to_write + self.buffer
    
    async def _write_to_opensearch(self, logs: List[Dict[str, Any]]) -> None:
        """Write logs to OpenSearch using bulk API.
        
        Args:
            logs: List of log entries to write
            
        Raises:
            OpenSearchException: If write fails
        """
        if not self.client:
            raise OpenSearchException("Not connected to OpenSearch")
        
        # Prepare bulk actions
        actions = []
        for log in logs:
            # Determine index name from timestamp
            index_name = self._get_index_name(log.get("timestamp"))
            
            # Create bulk action
            action = {
                "_index": index_name,
                "_source": log,
            }
            actions.append(action)
        
        # Execute bulk write (run in executor to avoid blocking)
        try:
            loop = asyncio.get_event_loop()
            
            def do_bulk():
                return bulk(
                    self.client,
                    actions,
                    raise_on_error=False,
                    raise_on_exception=False,
                )
            
            success, failed = await loop.run_in_executor(None, do_bulk)
            
            if failed:
                logger.warning(
                    "Some logs failed to write",
                    success=success,
                    failed=len(failed),
                )
            
            logger.info(
                "Logs written to OpenSearch",
                count=success,
                failed=len(failed) if failed else 0,
            )
            
        except Exception as e:
            logger.error(
                "Bulk write failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
    
    def _get_index_name(self, timestamp: Optional[str]) -> str:
        """Generate index name from timestamp.
        
        Creates time-based indices: logs-YYYY-MM-DD
        
        Args:
            timestamp: ISO format timestamp string
            
        Returns:
            Index name (e.g., "logs-2026-01-18")
        """
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return f"{self.index_prefix}-{dt.strftime('%Y-%m-%d')}"
            except (ValueError, AttributeError):
                pass
        
        # Fallback to current date
        return f"{self.index_prefix}-{datetime.utcnow().strftime('%Y-%m-%d')}"
    
    async def _flush_periodically(self) -> None:
        """Flush buffer periodically.
        
        This ensures logs are written even if batch size isn't reached.
        """
        while self.running:
            await asyncio.sleep(self.flush_interval)
            
            if self.buffer:
                await self._flush()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenSearch cluster health.
        
        Returns:
            Cluster health information
        """
        if not self.client:
            return {"status": "disconnected"}
        
        try:
            loop = asyncio.get_event_loop()
            health = await loop.run_in_executor(
                None, 
                self.client.cluster.health
            )
            return {
                "status": health.get("status"),
                "cluster_name": health.get("cluster_name"),
                "number_of_nodes": health.get("number_of_nodes"),
                "active_shards": health.get("active_shards"),
            }
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {"status": "error", "error": str(e)}
    
    def get_statistics(self) -> Dict[str, int]:
        """Get writer statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "logs_written": self.logs_written,
            "batches_written": self.batches_written,
            "write_failures": self.write_failures,
            "buffer_size": len(self.buffer),
        }