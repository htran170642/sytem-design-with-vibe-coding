"""
Application configuration using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union
import os

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str
    
    # Application
    APP_NAME: str = "Event Ticket Booking System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Waiting Room
    WAITING_ROOM_SESSION_DURATION: int = 600  # 10 minutes to complete booking
    
    # Booking Settings
    HOLD_DURATION_MINUTES: int = 5
    MAX_SEATS_PER_BOOKING: int = 10
    MAX_ACTIVE_HOLDS_PER_USER: int = 3

    # Background Workers
    HOLD_EXPIRY_CHECK_INTERVAL_SECONDS: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300
    REDIS_SEATS_TTL: int = 60
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "null",
    ]
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        # ✅ Try multiple locations for .env file
        env_file = None  # Will be set dynamically
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = 'ignore'

# ✅ Find .env file dynamically
def find_env_file():
    """Search for .env file in common locations"""
    import os
    from pathlib import Path
    
    # Possible locations
    locations = [
        Path.cwd() / '.env',  # Current directory
        Path(__file__).parent.parent.parent / '.env',  # Project root
        Path.home() / 'dev/practice/python/vide_coding_python/event_ticketing_system/.env',  # Absolute
    ]
    
    for loc in locations:
        if loc.exists():
            print(f"✅ Found .env at: {loc}")
            return str(loc)
    
    print(f"❌ .env not found in: {[str(l) for l in locations]}")
    return '.env'  # Fallback

# Set the env_file path
Settings.model_config['env_file'] = find_env_file()

# Global settings instance
settings = Settings()
