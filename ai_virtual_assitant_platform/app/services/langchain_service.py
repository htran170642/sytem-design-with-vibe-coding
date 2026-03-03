"""
LangChain Service
Integrates LangChain for advanced AI workflows
Phase 3, Step 5: Integrate LangChain for basic chains (QA, chat)
"""

from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LangChainService:
    """
    Service for LangChain-based AI operations
    
    Provides:
    - Conversational chains with memory
    - Question answering chains
    - Custom prompt chains
    """
    
    def __init__(self):
        """Initialize LangChain components"""
        
        # Create LangChain ChatOpenAI instance
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
            verbose=settings.LANGCHAIN_VERBOSE,
        )
        
        logger.info(
            "LangChain service initialized",
            extra={
                "model": settings.OPENAI_MODEL,
                "verbose": settings.LANGCHAIN_VERBOSE,
            },
        )
    
    def create_conversation_chain(
        self,
        system_message: str = "You are a helpful AI assistant.",
        memory_key: str = "chat_history",
    ) -> LLMChain:
        """
        Create a conversational chain with memory
        
        Args:
            system_message: System prompt for the conversation
            memory_key: Key for storing conversation history
            
        Returns:
            LLMChain with conversation memory
            
        Example:
            >>> chain = service.create_conversation_chain()
            >>> response = await chain.ainvoke({"input": "Hello!"})
            >>> print(response["text"])
        """
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name=memory_key),
            ("human", "{input}"),
        ])
        
        # Create memory
        memory = ConversationBufferMemory(
            memory_key=memory_key,
            return_messages=True,
        )
        
        # Create chain
        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            memory=memory,
            verbose=settings.LANGCHAIN_VERBOSE,
        )
        
        logger.debug("Created conversation chain with memory")
        
        return chain
    
    def create_qa_chain(
        self,
        system_message: str = "Answer the question based on the provided context.",
    ) -> LLMChain:
        """
        Create a question-answering chain
        
        Args:
            system_message: System prompt for QA
            
        Returns:
            LLMChain for question answering
            
        Example:
            >>> chain = service.create_qa_chain()
            >>> response = await chain.ainvoke({
            ...     "context": "Python was created in 1991",
            ...     "question": "When was Python created?"
            ... })
        """
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", "Context:\n{context}\n\nQuestion: {question}"),
        ])
        
        # Create chain
        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=settings.LANGCHAIN_VERBOSE,
        )
        
        logger.debug("Created QA chain")
        
        return chain
    
    def create_custom_chain(
        self,
        prompt_template: str,
        input_variables: List[str],
    ) -> LLMChain:
        """
        Create a custom chain with specified prompt template
        
        Args:
            prompt_template: Template string with variables
            input_variables: List of variable names in template
            
        Returns:
            LLMChain with custom prompt
            
        Example:
            >>> chain = service.create_custom_chain(
            ...     prompt_template="Translate to {language}: {text}",
            ...     input_variables=["language", "text"]
            ... )
            >>> response = await chain.ainvoke({
            ...     "language": "French",
            ...     "text": "Hello world"
            ... })
        """
        from langchain.prompts import PromptTemplate
        
        # Create prompt
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=input_variables,
        )
        
        # Create chain
        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=settings.LANGCHAIN_VERBOSE,
        )
        
        logger.debug(
            "Created custom chain",
            extra={"input_variables": input_variables},
        )
        
        return chain
    
    async def simple_invoke(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Simple invoke - send prompt and get response
        
        Args:
            prompt: The prompt text
            **kwargs: Additional parameters for the LLM
            
        Returns:
            Response text
            
        Example:
            >>> response = await service.simple_invoke("What is Python?")
        """
        messages = [HumanMessage(content=prompt)]
        
        response = await self.llm.ainvoke(messages, **kwargs)
        
        return response.content
    
    async def chat_with_history(
        self,
        message: str,
        history: List[Dict[str, str]],
        system_message: Optional[str] = None,
    ) -> str:
        """
        Chat with conversation history
        
        Args:
            message: New user message
            history: Previous conversation history
            system_message: Optional system message
            
        Returns:
            AI response
            
        Example:
            >>> history = [
            ...     {"role": "user", "content": "Hi, I'm Alice"},
            ...     {"role": "assistant", "content": "Hello Alice!"}
            ... ]
            >>> response = await service.chat_with_history(
            ...     message="What's my name?",
            ...     history=history
            ... )
        """
        # Build messages
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        # Add history
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add new message
        messages.append(HumanMessage(content=message))
        
        # Get response
        response = await self.llm.ainvoke(messages)
        
        return response.content


# Global instance
_langchain_service: Optional[LangChainService] = None


def get_langchain_service() -> LangChainService:
    """
    Get or create LangChain service instance (singleton)
    
    Returns:
        LangChainService instance
        
    Example:
        >>> service = get_langchain_service()
        >>> chain = service.create_conversation_chain()
    """
    global _langchain_service
    
    if _langchain_service is None:
        _langchain_service = LangChainService()
    
    return _langchain_service