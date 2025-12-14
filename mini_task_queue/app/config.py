from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Worker
    worker_concurrency: int = 5
    worker_queue_name: str = "queue:default"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()