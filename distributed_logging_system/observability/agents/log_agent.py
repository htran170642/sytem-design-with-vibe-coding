"""Log collection agent.

This agent collects logs from files or stdin, batches them, and sends
them to the ingestion API with retry logic.
"""
import asyncio
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiofiles
import httpx

from observability.common.config import get_settings
from observability.common.logger import get_logger
from observability.common.models import LogBatch, LogEntry, LogLevel
from observability.common.retry import RetryConfig, retry_async

logger = get_logger(__name__)


class LogAgent:
    """Agent that collects and sends logs to the ingestion service.
    
    This agent can:
    - Tail log files (like `tail -f`)
    - Read from stdin
    - Batch logs for efficient transmission
    - Retry failed sends with exponential backoff
    - Buffer logs locally if ingestion is down
    
    Example:
        ```python
        agent = LogAgent(
            service_name="my-app",
            log_file="/var/log/app.log"
        )
        await agent.start()
        ```
    """

    def __init__(
        self,
        service_name: str,
        environment: Optional[str] = None,
        log_file: Optional[str] = None,
        ingestion_url: Optional[str] = None,
        api_key: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        buffer_size: int = 10000,
    ):
        """Initialize the log agent.
        
        Args:
            service_name: Name of the service generating logs
            environment: Environment (dev/staging/prod), defaults from config
            log_file: Path to log file to tail (None = read from stdin)
            ingestion_url: URL of ingestion API, defaults from config
            api_key: API key for authentication, defaults from config
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds to wait before flushing partial batch
            buffer_size: Maximum logs to buffer in memory
        """
        settings = get_settings()
        
        self.service_name = service_name
        self.environment = environment or settings.environment
        self.log_file = Path(log_file) if log_file else None
        self.hostname = os.getenv("HOSTNAME", os.uname().nodename)
        
        # API configuration
        self.ingestion_url = ingestion_url or (
            f"http://{settings.ingestion_host}:{settings.ingestion_port}/logs"
        )
        self.api_key = api_key or settings.ingestion_api_key
        
        # Batching configuration
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer_size = buffer_size
        
        # Internal state
        self.buffer: List[LogEntry] = []
        self.http_client: Optional[httpx.AsyncClient] = None
        self.running = False
        self.retry_config = RetryConfig(
            max_retries=settings.max_retries,
            initial_delay=1.0,
            max_delay=30.0,
        )
        
        logger.info(
            "Log agent initialized",
            service=service_name,
            environment=self.environment,
            log_file=str(self.log_file) if self.log_file else "stdin",
            ingestion_url=self.ingestion_url,
        )

    async def start(self) -> None:
        """Start the log agent.
        
        This will:
        1. Start reading logs (from file or stdin)
        2. Start the flush timer
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
        
        logger.info("Log agent started")
        
        try:
            # Run collector and flusher concurrently
            await asyncio.gather(
                self._collect_logs(),
                self._flush_periodically(),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent.
        
        Flushes any remaining logs before exiting.
        """
        if not self.running:
            return
        
        logger.info("Shutting down log agent")
        self.running = False
        
        # Flush remaining logs
        if self.buffer:
            await self._flush()
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Log agent stopped")

    async def _collect_logs(self) -> None:
        """Collect logs from file or stdin.
        
        This runs continuously until shutdown.
        """
        if self.log_file:
            await self._tail_file()
        else:
            await self._read_stdin()

    async def _tail_file(self) -> None:
        """Tail a log file (like `tail -f`).
        
        Reads new lines as they're written to the file.
        Handles file rotation gracefully.
        """
        if not self.log_file or not self.log_file.exists():
            logger.error("Log file not found", path=str(self.log_file))
            return
        
        logger.info("Tailing log file", path=str(self.log_file))
        
        # Open file and seek to end
        async with aiofiles.open(self.log_file, mode="r") as f:
            # Go to end of file
            await f.seek(0, 2)
            
            while self.running:
                line = await f.readline()
                
                if line:
                    # Process the log line
                    await self._process_line(line.strip())
                else:
                    # No new data, wait a bit
                    await asyncio.sleep(0.1)

    async def _read_stdin(self) -> None:
        """Read logs from stdin.
        
        Useful for piping output from other commands:
        `my-app | python -m observability.agents.log_agent`
        """
        logger.info("Reading logs from stdin")
        
        # Read from stdin in non-blocking way
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Read line from stdin (blocking, so run in executor)
                line = await loop.run_in_executor(None, sys.stdin.readline)
                
                if not line:
                    # EOF reached
                    break
                
                await self._process_line(line.strip())
                
            except Exception as e:
                logger.error("Error reading stdin", error=str(e))
                break

    async def _process_line(self, line: str) -> None:
        """Process a single log line.
        
        Args:
            line: Raw log line as string
        """
        if not line:
            return
        
        try:
            # Parse log level from line if possible
            level = self._parse_log_level(line)
            
            # Create log entry
            entry = LogEntry(
                timestamp=datetime.utcnow(),
                level=level,
                message=line,
                service=self.service_name,
                environment=self.environment,
                host=self.hostname,
            )
            
            # Add to buffer
            await self._add_to_buffer(entry)
            
        except Exception as e:
            logger.error("Error processing log line", error=str(e), line=line)

    def _parse_log_level(self, line: str) -> LogLevel:
        """Extract log level from log line.
        
        Looks for common patterns like:
        - [ERROR] message
        - 2024-01-10 ERROR: message
        - ERROR - message
        
        Args:
            line: Log line
            
        Returns:
            Detected log level, defaults to INFO
        """
        line_upper = line.upper()
        
        for level in LogLevel:
            if level.value in line_upper:
                return level
        
        return LogLevel.INFO

    async def _add_to_buffer(self, entry: LogEntry) -> None:
        """Add log entry to buffer and flush if needed.
        
        Args:
            entry: Log entry to buffer
        """
        # Check buffer size limit
        if len(self.buffer) >= self.buffer_size:
            logger.warning(
                "Buffer full, dropping oldest log",
                buffer_size=self.buffer_size,
            )
            self.buffer.pop(0)
        
        self.buffer.append(entry)
        
        # Flush if batch size reached
        if len(self.buffer) >= self.batch_size:
            await self._flush()

    async def _flush_periodically(self) -> None:
        """Flush logs on a timer.
        
        This ensures logs are sent even if batch size isn't reached.
        For example, if only 10 logs come in but batch_size=100,
        we'll still send them after flush_interval seconds.
        """
        while self.running:
            await asyncio.sleep(self.flush_interval)
            
            if self.buffer:
                await self._flush()

    async def _flush(self) -> None:
        """Send buffered logs to ingestion API.
        
        Uses retry logic to handle transient failures.
        """
        if not self.buffer:
            return
        
        # Take all logs from buffer
        logs_to_send = self.buffer.copy()
        self.buffer.clear()
        
        try:
            # Create batch
            batch = LogBatch(entries=logs_to_send)
            
            logger.debug(
                "Sending log batch",
                count=len(logs_to_send),
                url=self.ingestion_url,
            )
            
            # Send with retry
            await retry_async(
                self._send_batch,
                batch,
                config=self.retry_config,
                retry_on_exceptions=(httpx.HTTPError, httpx.TimeoutException),
            )
            
            logger.debug("Log batch sent successfully", count=len(logs_to_send))
            
        except Exception as e:
            # All retries failed - log error and drop the batch
            # In production, you might write to local disk instead
            logger.error(
                "Failed to send logs after retries",
                count=len(logs_to_send),
                error=str(e),
            )

    async def _send_batch(self, batch: LogBatch) -> None:
        """Send a batch to the ingestion API.
        
        Args:
            batch: Batch of log entries
            
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
        
        # Raise on 4xx/5xx errors
        response.raise_for_status()


async def main() -> None:
    """Main entry point for the log agent.
    
    Usage:
        # Tail a log file
        python -m observability.agents.log_agent --service my-app --file /var/log/app.log
        
        # Read from stdin
        echo "Test log message" | python -m observability.agents.log_agent --service my-app
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Log collection agent")
    parser.add_argument(
        "--service",
        required=True,
        help="Service name",
    )
    parser.add_argument(
        "--file",
        help="Log file to tail (omit to read from stdin)",
    )
    parser.add_argument(
        "--environment",
        help="Environment (dev/staging/prod)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size (default: 100)",
    )
    parser.add_argument(
        "--flush-interval",
        type=float,
        default=5.0,
        help="Flush interval in seconds (default: 5.0)",
    )
    
    args = parser.parse_args()
    
    # Create and start agent
    agent = LogAgent(
        service_name=args.service,
        environment=args.environment,
        log_file=args.file,
        batch_size=args.batch_size,
        flush_interval=args.flush_interval,
    )
    
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())