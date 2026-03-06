from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379")

    # PostgreSQL
    database_url: str = Field(
        default="postgresql://flash_sale:flash_sale@localhost:5432/flash_sale"
    )

    # API server
    api_host: str = Field(default="0.0.0.0")  # noqa: S104
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)

    # Flash sale
    stock_key_prefix: str = Field(default="stock")
    idempotency_key_prefix: str = Field(default="idempotency")
    idempotency_ttl_seconds: int = Field(default=86400)
    orders_stream: str = Field(default="orders")
    orders_consumer_group: str = Field(default="order-workers")
    dlq_stream: str = Field(default="orders.dlq")
    # ~ prefix trims to approximate length (faster than exact MAXLEN)
    stream_max_len: int = Field(default=1_000_000)
    # Worker instance name — override per-pod in k8s via env var
    worker_consumer_name: str = Field(default="worker-1")
    # Unclaimed messages older than this (ms) are reclaimed on restart
    stream_claim_min_idle_ms: int = Field(default=30_000)

    # Rate limiting
    rate_limit_per_user: int = Field(default=10)
    rate_limit_global: int = Field(default=100_000)

    # Observability
    env: str = Field(default="development")
    log_level: str = Field(default="INFO")


settings = Settings()
