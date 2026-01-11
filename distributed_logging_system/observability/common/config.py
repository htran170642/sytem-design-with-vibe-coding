"""Configuration management using pydantic-settings."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="observability-platform")

    # Ingestion Service
    ingestion_host: str = Field(default="0.0.0.0")
    ingestion_port: int = Field(default=8000)
    ingestion_api_key: str = Field(default="development-key")

    # Query Service
    query_host: str = Field(default="0.0.0.0")
    query_port: int = Field(default=8001)

    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_consumer_group: str = Field(default="observability-processors")
    kafka_log_topic: str = Field(default="logs.raw")
    kafka_metrics_topic: str = Field(default="metrics.raw")
    kafka_events_topic: str = Field(default="events.raw")

    # OpenSearch
    opensearch_host: str = Field(default="localhost")
    opensearch_port: int = Field(default=9200)
    opensearch_username: str = Field(default="admin")
    opensearch_password: str = Field(default="admin")
    opensearch_use_ssl: bool = Field(default=False)
    opensearch_logs_index: str = Field(default="logs")
    opensearch_metrics_index: str = Field(default="metrics")

    # Redis
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: Optional[str] = Field(default=None)

    # S3 / MinIO
    s3_endpoint: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="observability-data")
    s3_region: str = Field(default="us-east-1")

    # Retention
    hot_retention_days: int = Field(default=7)
    warm_retention_days: int = Field(default=30)

    # Rate Limiting
    rate_limit_requests: int = Field(default=1000)
    rate_limit_window: int = Field(default=60)

    # Processing
    batch_size: int = Field(default=100)
    flush_interval_seconds: int = Field(default=5)
    max_retries: int = Field(default=3)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
