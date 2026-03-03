"""
AI Service
Orchestrates LLM calls with retry logic, prompt templates, and error handling
Phase 3, Step 4: Build AI service layer (LLM orchestration)
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncIterator

from openai import OpenAIError

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.exceptions import LLMError
from app.services.metrics_service import (
    llm_cost_dollars_total,
    llm_request_duration_seconds,
    llm_requests_total,
    llm_tokens_total,
)
from app.services.openai_client import get_openai_client
from app.services.prompt_templates import PromptTemplateManager, build_conversation_messages
from app.services.token_tracker import get_token_tracker
from app.utils.retry import retry_with_exponential_backoff, with_timeout

logger = get_logger(__name__)


class AIService:
    """
    High-level AI service for LLM operations
    
    Orchestrates:
    - OpenAI client
    - Retry logic
    - Prompt templates
    - Error handling
    - Token tracking
    """
    
    def __init__(self):
        """Initialize AI service with OpenAI client"""
        self.client = get_openai_client()
        self.template_manager = PromptTemplateManager
        self.token_tracker = get_token_tracker()
        
        logger.info(
            "AI Service initialized",
            extra={
                "model": self.client.default_model,
                "temperature": self.client.default_temperature,
            },
        )
    
    @retry_with_exponential_backoff(max_retries=3, initial_delay=1.0)
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Dict:
        """
        Generate chat completion with retry logic
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            model: Model to use (defaults to configured model)
            
        Returns:
            Dict with response and metadata:
            {
                "message": "AI response text",
                "model": "gpt-3.5-turbo",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                    "total_tokens": 150
                }
            }
            
        Raises:
            LLMError: If API call fails after retries
        """
        start_time = time.time()
        
        try:
            # Use defaults if not provided
            model = model or self.client.default_model
            temperature = temperature if temperature is not None else self.client.default_temperature
            max_tokens = max_tokens or self.client.default_max_tokens
            
            logger.info(
                "Starting chat completion",
                extra={
                    "model": model,
                    "messages_count": len(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            
            # Call OpenAI API with timeout
            response = await with_timeout(
                self.client.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=settings.OPENAI_TIMEOUT,
                operation_name="chat_completion"
            )
            
            # Extract response data
            choice = response.choices[0]
            usage = response.usage
            
            result = {
                "message": choice.message.content,
                "model": response.model,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
            }
            
            elapsed = time.time() - start_time
            used_model = response.model

            # Track token usage and cost
            token_usage = self.token_tracker.track_request(
                model=used_model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=elapsed * 1000,  # Convert to milliseconds
            )

            # Record Prometheus metrics
            llm_requests_total.labels(model=used_model, status="success").inc()
            llm_request_duration_seconds.labels(model=used_model).observe(elapsed)
            llm_tokens_total.labels(model=used_model, token_type="prompt").inc(
                usage.prompt_tokens
            )
            llm_tokens_total.labels(model=used_model, token_type="completion").inc(
                usage.completion_tokens
            )
            llm_cost_dollars_total.labels(model=used_model).inc(token_usage.total_cost)

            logger.info(
                "Chat completion successful",
                extra={
                    "model": result["model"],
                    "tokens_used": result["usage"]["total_tokens"],
                    "cost_usd": round(token_usage.total_cost, 6),
                    "finish_reason": result["finish_reason"],
                    "duration_seconds": round(elapsed, 2),
                },
            )

            return result

        except asyncio.TimeoutError as e:
            elapsed = time.time() - start_time
            llm_requests_total.labels(model=model, status="timeout").inc()
            llm_request_duration_seconds.labels(model=model).observe(elapsed)
            logger.error("Chat completion timeout", exc_info=True)
            raise LLMError(
                message=f"Request timed out after {settings.OPENAI_TIMEOUT}s",
                details={"timeout": settings.OPENAI_TIMEOUT},
            )
        except OpenAIError as e:
            elapsed = time.time() - start_time
            llm_requests_total.labels(model=model, status="error").inc()
            llm_request_duration_seconds.labels(model=model).observe(elapsed)
            logger.error("OpenAI API error", exc_info=True)
            raise LLMError(
                message="AI service error occurred",
                details={"error": str(e)},
            )
        except Exception as e:
            elapsed = time.time() - start_time
            llm_requests_total.labels(model=model, status="error").inc()
            llm_request_duration_seconds.labels(model=model).observe(elapsed)
            logger.error("Unexpected error in chat completion", exc_info=True)
            raise LLMError(
                message="An unexpected error occurred",
                details={"error": str(e)},
            )
    
    async def simple_chat(
        self,
        message: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Simple chat - send one message, get one response
        
        Args:
            message: User message
            system_message: Optional system message
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            AI response text
            
        Example:
            >>> response = await ai_service.simple_chat("What is Python?")
            >>> print(response)
            "Python is a programming language..."
        """
        # Build messages using template
        template = self.template_manager.get_template("general_chat")
        
        if system_message:
            # Use custom system message
            messages = build_conversation_messages(
                messages=[{"role": "user", "content": message}],
                system_message=system_message
            )
        else:
            # Use template's system message
            messages = template.build_messages(message=message)
        
        # Get completion
        result = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return result["message"]
    
    async def qa_with_context(
        self,
        question: str,
        context: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Question answering with context (RAG)
        
        Args:
            question: User's question
            context: Context from document search
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Dict with answer and metadata
            
        Example:
            >>> result = await ai_service.qa_with_context(
            ...     question="What is Python?",
            ...     context="Python is a programming language..."
            ... )
            >>> print(result["message"])
            "Based on the context, Python is a programming language..."
        """
        # Build messages using QA template
        template = self.template_manager.get_template("qa_with_context")
        messages = template.build_messages(question=question, context=context)
        
        # Get completion
        result = await self.chat_completion(
            messages=messages,
            temperature=temperature or 0.3,  # Lower temp for factual Q&A
            max_tokens=max_tokens,
        )
        
        return result
    
    async def conversation(
        self,
        message: str,
        history: List[Dict[str, str]],
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Continue a conversation with history
        
        Args:
            message: New user message
            history: Previous conversation messages
            system_message: Optional system message
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Dict with response and metadata
            
        Example:
            >>> history = [
            ...     {"role": "user", "content": "Hi, I'm Alice"},
            ...     {"role": "assistant", "content": "Hello Alice!"}
            ... ]
            >>> result = await ai_service.conversation(
            ...     message="What's my name?",
            ...     history=history
            ... )
            >>> print(result["message"])
            "Your name is Alice."
        """
        # Add new message to history
        conversation = history.copy()
        conversation.append({"role": "user", "content": message})
        
        # Build messages with optional system message
        if system_message:
            messages = build_conversation_messages(
                messages=conversation,
                system_message=system_message
            )
        else:
            # Use default conversation template system message
            template = self.template_manager.get_template("conversation_with_history")
            messages = build_conversation_messages(
                messages=conversation,
                system_message=template.system_message
            )
        
        # Get completion
        result = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return result
    
    @retry_with_exponential_backoff(max_retries=3, initial_delay=1.0)
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion response
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            model: Model to use
            
        Yields:
            Chunks of response text
            
        Example:
            >>> async for chunk in ai_service.stream_chat_completion(messages):
            ...     print(chunk, end="", flush=True)
            "Hello" " " "world" "!"
        """
        try:
            model = model or self.client.default_model
            temperature = temperature if temperature is not None else self.client.default_temperature
            max_tokens = max_tokens or self.client.default_max_tokens
            
            logger.info(
                "Starting streaming chat completion",
                extra={"model": model, "messages_count": len(messages)},
            )
            
            # Call OpenAI API with streaming
            stream = await self.client.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            logger.info("Streaming chat completion finished")
            
        except OpenAIError as e:
            logger.error("Error in streaming completion", exc_info=True)
            raise LLMError(
                message="Streaming error occurred",
                details={"error": str(e)},
            )
    
    def get_usage_stats(self) -> Dict:
        """
        Get token usage and cost statistics
        
        Returns:
            Dict with usage statistics
            
        Example:
            >>> stats = ai_service.get_usage_stats()
            >>> print(f"Total cost: ${stats['overall']['total_cost_usd']}")
            >>> print(f"Total requests: {stats['overall']['total_requests']}")
        """
        return self.token_tracker.get_stats()
    
    def reset_usage_stats(self):
        """
        Reset token usage statistics
        
        Useful for testing or periodic resets
        """
        self.token_tracker.reset_stats()
        logger.info("Usage statistics reset")


# Global instance
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """
    Get or create AI service instance (singleton)
    
    Returns:
        AIService instance
        
    Example:
        >>> ai_service = get_ai_service()
        >>> response = await ai_service.simple_chat("Hello!")
    """
    global _ai_service
    
    if _ai_service is None:
        _ai_service = AIService()
    
    return _ai_service