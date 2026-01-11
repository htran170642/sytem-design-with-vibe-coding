"""Data models for logs, metrics, and events.

These Pydantic models define the structure and validation rules for all data
flowing through the observability platform.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(BaseModel):
    """A single log entry.
    
    This represents a log line from an application with metadata
    about where and when it occurred.
    
    Attributes:
        timestamp: When the log was generated (ISO format)
        level: Severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: The actual log message
        service: Name of the service that generated the log
        environment: Deployment environment (dev, staging, prod)
        host: Hostname or container ID where log originated
        labels: Additional key-value metadata
        trace_id: Optional distributed trace ID for correlation
        span_id: Optional span ID within a trace
    """

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the log was generated"
    )
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log severity level"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Log message content"
    )
    service: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Service name"
    )
    environment: str = Field(
        default="development",
        description="Environment (dev, staging, prod)"
    )
    host: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostname or container ID"
    )
    labels: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata labels"
    )
    trace_id: Optional[str] = Field(
        default=None,
        description="Distributed trace ID"
    )
    span_id: Optional[str] = Field(
        default=None,
        description="Span ID within trace"
    )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator("message")
    def validate_message(cls, v: str) -> str:
        """Ensure message is not just whitespace."""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace")
        return v.strip()


class MetricType(str, Enum):
    """Types of metrics we can collect."""

    COUNTER = "counter"  # Monotonically increasing value
    GAUGE = "gauge"      # Point-in-time value that can go up or down
    HISTOGRAM = "histogram"  # Distribution of values


class MetricEntry(BaseModel):
    """A single metric data point.
    
    Metrics represent numerical measurements over time, like CPU usage,
    request count, or memory consumption.
    
    Attributes:
        timestamp: When the metric was collected
        name: Metric name (e.g., 'cpu_usage_percent', 'request_count')
        value: The numerical value
        metric_type: Type of metric (counter, gauge, histogram)
        service: Name of the service
        environment: Deployment environment
        host: Hostname where metric was collected
        labels: Additional dimensions (e.g., {'endpoint': '/api/users'})
        unit: Optional unit of measurement (e.g., 'bytes', 'seconds')
    """

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When metric was collected"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Metric name"
    )
    value: float = Field(
        ...,
        description="Metric value"
    )
    metric_type: MetricType = Field(
        default=MetricType.GAUGE,
        description="Type of metric"
    )
    service: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Service name"
    )
    environment: str = Field(
        default="development",
        description="Environment"
    )
    host: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostname"
    )
    labels: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metric labels/dimensions"
    )
    unit: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Unit of measurement"
    )

    @validator("metric_type", pre=True)
    def normalize_metric_type(cls, v):
        """Normalize metric type to lowercase to accept both 'GAUGE' and 'gauge'."""
        if isinstance(v, str):
            return v.lower()
        return v

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Ensure metric name follows naming conventions."""
        # Metric names should be lowercase with underscores
        cleaned = v.lower().replace("-", "_").replace(" ", "_")
        if not cleaned.replace("_", "").replace(".", "").isalnum():
            raise ValueError(
                "Metric name must contain only alphanumeric characters, dots, and underscores"
            )
        return cleaned


class LogBatch(BaseModel):
    """A batch of log entries sent together.
    
    Batching reduces network overhead by sending multiple logs in one request.
    """

    entries: list[LogEntry] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of log entries"
    )
    agent_version: str = Field(
        default="1.0.0",
        description="Version of the log agent"
    )


class MetricBatch(BaseModel):
    """A batch of metric entries sent together."""

    entries: list[MetricEntry] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of metric entries"
    )
    agent_version: str = Field(
        default="1.0.0",
        description="Version of the metrics agent"
    )