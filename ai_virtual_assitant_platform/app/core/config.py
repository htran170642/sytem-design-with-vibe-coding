"""
Application Settings Module
Manages configuration from environment variables using Pydantic Settings
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ============================================
    # Application Settings
    # ============================================
    APP_NAME: str = "AIVA"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = True
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # ============================================
    # Security & Authentication
    # ============================================
    SECRET_KEY: str = Field(..., min_length=32)
    API_KEY: str = Field(..., min_length=16)

    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # ============================================
    # OpenAI Configuration
    # ============================================
    OPENAI_API_KEY: str = Field(..., min_length=20)
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: int = Field(default=2000, ge=1, le=4096)
    OPENAI_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    OPENAI_TIMEOUT: int = Field(default=30, ge=1, le=300)
    OPENAI_MAX_RETRIES: int = Field(default=2, ge=0, le=5)

    # Embedding Model
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    
    # ============================================
    # LangChain Configuration
    # ============================================
    LANGCHAIN_VERBOSE: bool = Field(default=False, description="Enable LangChain verbose logging")
    LANGCHAIN_TRACING: bool = Field(default=False, description="Enable LangChain tracing")

    # ============================================
    # Database Configuration
    # ============================================
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v

    # ============================================
    # Redis Configuration
    # ============================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = Field(default=6379, ge=1, le=65535)
    REDIS_DB: int = Field(default=0, ge=0, le=15)
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cache Settings
    CACHE_TTL: int = Field(default=3600, ge=0)       # legacy default (1h)
    CACHE_ENABLED: bool = True

    # Per-type cache TTLs (seconds)
    CACHE_EMBEDDING_TTL: int = Field(default=86400, ge=0)    # 24h — embeddings rarely change
    CACHE_AI_RESPONSE_TTL: int = Field(default=3600, ge=0)   # 1h  — AI answers
    CACHE_FAQ_TTL: int = Field(default=1800, ge=0)           # 30min — frequent queries
    CACHE_DEFAULT_TTL: int = Field(default=600, ge=0)        # 10min — fallback

    # ============================================
    # Celery Configuration
    # ============================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ============================================
    # Vector Database (Qdrant)
    # ============================================
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = Field(default=6333, ge=1, le=65535)
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "aiva_documents_dev"
    QDRANT_VECTOR_SIZE: int = 1536

    # ============================================
    # Document Processing
    # ============================================
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = Field(default=10485760, ge=1024)  # 10MB default
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "txt", "docx", "md"]

    # Chunking Settings
    CHUNK_SIZE: int = Field(default=1000, ge=100, le=10000)
    CHUNK_OVERLAP: int = Field(default=200, ge=0, le=1000)

    # ============================================
    # Rate Limiting
    # ============================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, ge=1)

    # ============================================
    # Celery & Background Jobs
    # ============================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set True for testing (synchronous)
    CELERY_TASK_EAGER_PROPAGATES: bool = True
    
    # Task timeouts
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300  # 5 minutes soft limit
    CELERY_TASK_TIME_LIMIT: int = 600  # 10 minutes hard limit

    # ============================================
    # Monitoring & Observability
    # ============================================
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = Field(default=9090, ge=1, le=65535)

    # Logging
    LOG_FORMAT: str = Field(default="json", pattern="^(json|text)$")
    LOG_FILE: str = "./logs/aiva.log"
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "30 days"

    # ============================================
    # Feature Flags
    # ============================================
    ENABLE_DOCS: bool = True
    ENABLE_RAG: bool = True
    ENABLE_BACKGROUND_JOBS: bool = True
    ENABLE_CACHING: bool = True

    # ============================================
    # Development Settings
    # ============================================
    FLOWER_PORT: int = Field(default=5555, ge=1, le=65535)
    FLOWER_BASIC_AUTH: Optional[str] = None

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra environment variables
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.APP_ENV == "development"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic)"""
        return self.DATABASE_URL.replace("+asyncpg", "")


# Create global settings instance
settings = Settings()


# Export for easy imports
__all__ = ["settings", "Settings"]