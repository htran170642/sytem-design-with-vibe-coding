"""
AI Schemas
Pydantic schemas for AI/LLM endpoints
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate message role"""
        allowed_roles = ["user", "assistant", "system"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="User message to send to AI"
    )
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID")
    stream: bool = Field(default=False, description="Whether to stream the response")
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature (0.0 to 2.0)"
    )
    max_tokens: Optional[int] = Field(
        default=None, ge=1, le=4000, description="Maximum tokens in response"
    )
    use_rag: bool = Field(default=True, description="Whether to use RAG for context")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is machine learning?",
                "conversation_id": "conv_123",
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 500,
                "use_rag": True,
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""

    message: str = Field(..., description="AI response message")
    conversation_id: str = Field(..., description="Conversation ID")
    model: str = Field(..., description="Model used for generation")
    usage: Dict[str, int] = Field(..., description="Token usage statistics")
    sources: Optional[List[Dict[str, Any]]] = Field(
        None, description="Sources used for RAG (if applicable)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Machine learning is a subset of artificial intelligence...",
                "conversation_id": "conv_123",
                "model": "gpt-3.5-turbo",
                "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                "sources": [
                    {
                        "document_id": "doc_456",
                        "content": "Machine learning algorithms...",
                        "relevance_score": 0.92,
                    }
                ],
            }
        }


class CompletionRequest(BaseModel):
    """Request model for text completion endpoint"""

    prompt: str = Field(..., min_length=1, max_length=4000, description="Prompt text")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=500, ge=1, le=4000)
    stop: Optional[List[str]] = Field(None, description="Stop sequences")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Complete this sentence: The future of AI is",
                "temperature": 0.7,
                "max_tokens": 100,
                "stop": ["\n", "."],
            }
        }


class CompletionResponse(BaseModel):
    """Response model for completion endpoint"""

    text: str = Field(..., description="Completed text")
    model: str = Field(..., description="Model used")
    usage: Dict[str, int] = Field(..., description="Token usage")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "The future of AI is bright and full of possibilities",
                "model": "gpt-3.5-turbo",
                "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            }
        }