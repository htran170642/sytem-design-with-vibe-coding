"""
Application configuration
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Real-time Chat API"
    APP_VERSION: str = "2.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/chatdb"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Connection Pool
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES: int = 10
    RATE_LIMIT_WINDOW: int = 60
    RATE_LIMIT_API: int = 100
    RATE_LIMIT_REGISTER: int = 3
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_PING_TIMEOUT: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()