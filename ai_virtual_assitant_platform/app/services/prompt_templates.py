"""
Prompt Templates
Manages prompt templates for AI interactions
Phase 3, Step 3: Create prompt templates (system / user / context)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class PromptRole(str, Enum):
    """Message roles in conversation"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class PromptTemplate:
    """
    Template for AI prompts
    
    Attributes:
        name: Template identifier
        system_message: System instructions
        user_template: User message template with placeholders
        description: What this template is for
    """
    name: str
    system_message: str
    user_template: str
    description: str = ""
    
    def format_user_message(self, **kwargs) -> str:
        """
        Format user message with provided values
        
        Args:
            **kwargs: Values to fill template placeholders
            
        Returns:
            Formatted user message
            
        Example:
            >>> template = PromptTemplate(
            ...     name="qa",
            ...     user_template="Question: {question}\\nContext: {context}"
            ... )
            >>> template.format_user_message(
            ...     question="What is AI?",
            ...     context="AI stands for..."
            ... )
            "Question: What is AI?\\nContext: AI stands for..."
        """
        try:
            return self.user_template.format(**kwargs)
        except KeyError as e:
            logger.error(
                f"Missing required placeholder in template '{self.name}': {e}",
                extra={"template": self.name, "missing_key": str(e)},
            )
            raise ValueError(f"Missing required placeholder: {e}")
    
    def build_messages(self, **kwargs) -> List[Dict[str, str]]:
        """
        Build complete message list for API call
        
        Args:
            **kwargs: Values for user message template
            
        Returns:
            List of message dicts for OpenAI API
            
        Example:
            >>> messages = template.build_messages(question="What is AI?")
            >>> # Returns:
            >>> # [
            >>> #     {"role": "system", "content": "You are..."},
            >>> #     {"role": "user", "content": "Question: What is AI?"}
            >>> # ]
        """
        messages = []
        
        # Add system message if present
        if self.system_message:
            messages.append({
                "role": PromptRole.SYSTEM,
                "content": self.system_message,
            })
        
        # Add formatted user message
        user_content = self.format_user_message(**kwargs)
        messages.append({
            "role": PromptRole.USER,
            "content": user_content,
        })
        
        return messages


class PromptTemplateManager:
    """
    Manager for prompt templates
    
    Provides predefined templates for common use cases:
    - General chat
    - Question answering with context (RAG)
    - Summarization
    - Code generation
    """
    
    # Default templates
    TEMPLATES = {
        "general_chat": PromptTemplate(
            name="general_chat",
            system_message=(
                "You are AIVA (AI Virtual Assistant), a helpful, knowledgeable, and friendly AI assistant. "
                "You provide accurate, concise, and helpful responses. "
                "If you don't know something, you admit it rather than making up information."
            ),
            user_template="{message}",
            description="General purpose chat assistant",
        ),
        
        "qa_with_context": PromptTemplate(
            name="qa_with_context",
            system_message=(
                "You are AIVA, an AI assistant that answers questions based on provided context. "
                "Use the given context to answer the user's question. "
                "If the context doesn't contain relevant information, say so. "
                "Always cite which parts of the context you used."
            ),
            user_template=(
                "Context:\n"
                "{context}\n\n"
                "Question: {question}\n\n"
                "Please answer based on the context above."
            ),
            description="Question answering with RAG context",
        ),
        
        "summarization": PromptTemplate(
            name="summarization",
            system_message=(
                "You are a summarization expert. "
                "Create clear, concise summaries that capture the key points. "
                "Maintain the original meaning while being brief."
            ),
            user_template=(
                "Please summarize the following text:\n\n"
                "{text}\n\n"
                "Summary:"
            ),
            description="Text summarization",
        ),
        
        "code_generation": PromptTemplate(
            name="code_generation",
            system_message=(
                "You are an expert programmer. "
                "Write clean, well-documented, and efficient code. "
                "Include comments explaining key parts. "
                "Follow best practices and design patterns."
            ),
            user_template=(
                "Programming language: {language}\n\n"
                "Task: {task}\n\n"
                "Please provide the code:"
            ),
            description="Code generation assistance",
        ),
        
        "conversation_with_history": PromptTemplate(
            name="conversation_with_history",
            system_message=(
                "You are AIVA, a conversational AI assistant. "
                "Continue the conversation naturally, maintaining context from previous messages. "
                "Be helpful, friendly, and concise."
            ),
            user_template="{message}",
            description="Conversation with context history",
        ),
    }
    
    @classmethod
    def get_template(cls, name: str) -> PromptTemplate:
        """
        Get template by name
        
        Args:
            name: Template name
            
        Returns:
            PromptTemplate instance
            
        Raises:
            ValueError: If template not found
        """
        if name not in cls.TEMPLATES:
            available = ", ".join(cls.TEMPLATES.keys())
            raise ValueError(
                f"Template '{name}' not found. Available: {available}"
            )
        
        return cls.TEMPLATES[name]
    
    @classmethod
    def list_templates(cls) -> List[str]:
        """
        List all available template names
        
        Returns:
            List of template names
        """
        return list(cls.TEMPLATES.keys())
    
    @classmethod
    def add_custom_template(cls, template: PromptTemplate) -> None:
        """
        Add a custom template
        
        Args:
            template: PromptTemplate to add
        """
        cls.TEMPLATES[template.name] = template
        logger.info(
            f"Added custom template: {template.name}",
            extra={"template_name": template.name},
        )


def build_conversation_messages(
    messages: List[Dict[str, str]],
    system_message: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Build message list with optional system message
    
    Args:
        messages: Existing conversation messages
        system_message: Optional system message to prepend
        
    Returns:
        Complete message list
        
    Example:
        >>> history = [
        ...     {"role": "user", "content": "Hello"},
        ...     {"role": "assistant", "content": "Hi there!"}
        ... ]
        >>> build_conversation_messages(
        ...     messages=history,
        ...     system_message="You are a helpful assistant"
        ... )
        [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    """
    result = []
    
    # Add system message first if provided
    if system_message:
        result.append({
            "role": PromptRole.SYSTEM,
            "content": system_message,
        })
    
    # Add conversation history
    result.extend(messages)
    
    return result


def format_context_for_rag(
    contexts: List[str],
    max_contexts: int = 5,
    separator: str = "\n\n---\n\n",
) -> str:
    """
    Format multiple context snippets for RAG
    
    Args:
        contexts: List of context strings (from vector search)
        max_contexts: Maximum number of contexts to include
        separator: Separator between contexts
        
    Returns:
        Formatted context string
        
    Example:
        >>> contexts = [
        ...     "AI is artificial intelligence",
        ...     "Machine learning is a subset of AI"
        ... ]
        >>> format_context_for_rag(contexts)
        "AI is artificial intelligence\\n\\n---\\n\\nMachine learning is a subset of AI"
    """
    # Limit number of contexts
    limited_contexts = contexts[:max_contexts]
    
    # Number each context for citation
    numbered_contexts = [
        f"[Context {i+1}]\n{ctx}"
        for i, ctx in enumerate(limited_contexts)
    ]
    
    return separator.join(numbered_contexts)