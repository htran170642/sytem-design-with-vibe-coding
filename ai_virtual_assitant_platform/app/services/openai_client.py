"""
OpenAI Client
Simple wrapper for OpenAI API client
Phase 3, Step 1: Integrate OpenAI / ChatGPT client
"""

from typing import Optional
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """
    Wrapper for OpenAI AsyncClient
    
    Provides:
    - Configured client instance
    - Settings from environment variables
    - Logging on initialization
    """
    
    def __init__(self):
        """Initialize OpenAI client with settings"""
        
        # Validate API key is configured
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured in environment")
        
        # Create AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
            max_retries=settings.OPENAI_MAX_RETRIES,
        )
        
        # Store default settings
        self.default_model = settings.OPENAI_MODEL
        self.default_temperature = settings.OPENAI_TEMPERATURE
        self.default_max_tokens = settings.OPENAI_MAX_TOKENS
        
        logger.info(
            "OpenAI client initialized",
            extra={
                "model": self.default_model,
                "temperature": self.default_temperature,
                "max_tokens": self.default_max_tokens,
                "timeout": settings.OPENAI_TIMEOUT,
                "max_retries": settings.OPENAI_MAX_RETRIES,
            },
        )


# Singleton instance
_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """
    Get OpenAI client instance (singleton pattern)
    
    Returns:
        OpenAIClient instance
        
    Example:
        >>> client = get_openai_client()
        >>> response = await client.client.chat.completions.create(...)
    """
    global _client
    
    if _client is None:
        _client = OpenAIClient()
    
    return _client