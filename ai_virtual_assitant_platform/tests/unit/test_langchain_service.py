"""
Tests for LangChain Service
"""

import pytest

from app.services.langchain_service import LangChainService, get_langchain_service


def test_langchain_service_singleton():
    """Test that get_langchain_service returns same instance"""
    
    service1 = get_langchain_service()
    service2 = get_langchain_service()
    
    assert service1 is service2
    print("✓ LangChain service is a singleton")


def test_langchain_service_initialization():
    """Test LangChain service initializes correctly"""
    
    service = get_langchain_service()
    
    assert service.llm is not None
    
    print("✓ LangChain service initializes with LLM")


def test_create_conversation_chain():
    """Test creating conversation chain"""
    
    service = get_langchain_service()
    
    chain = service.create_conversation_chain(
        system_message="You are a helpful assistant"
    )
    
    assert chain is not None
    assert chain.memory is not None
    assert chain.prompt is not None
    
    print("✓ Conversation chain created with memory")


def test_create_qa_chain():
    """Test creating QA chain"""
    
    service = get_langchain_service()
    
    chain = service.create_qa_chain()
    
    assert chain is not None
    assert chain.prompt is not None
    
    print("✓ QA chain created")


def test_create_custom_chain():
    """Test creating custom chain"""
    
    service = get_langchain_service()
    
    chain = service.create_custom_chain(
        prompt_template="Translate to {language}: {text}",
        input_variables=["language", "text"]
    )
    
    assert chain is not None
    assert chain.prompt is not None
    
    print("✓ Custom chain created")


def test_conversation_chain_has_memory():
    """Test that conversation chain maintains memory"""
    
    service = get_langchain_service()
    
    chain = service.create_conversation_chain()
    
    # Check memory exists
    assert hasattr(chain, 'memory')
    assert chain.memory is not None
    
    # Check memory is ConversationBufferMemory
    from langchain.memory import ConversationBufferMemory
    assert isinstance(chain.memory, ConversationBufferMemory)
    
    print("✓ Conversation chain has ConversationBufferMemory")


def test_qa_chain_has_correct_variables():
    """Test QA chain expects correct input variables"""
    
    service = get_langchain_service()
    
    chain = service.create_qa_chain()
    
    # Check input variables
    input_vars = chain.prompt.input_variables
    
    assert "context" in input_vars
    assert "question" in input_vars
    
    print("✓ QA chain has correct input variables (context, question)")


def test_custom_chain_respects_variables():
    """Test custom chain uses specified variables"""
    
    service = get_langchain_service()
    
    variables = ["language", "text"]
    chain = service.create_custom_chain(
        prompt_template="Translate to {language}: {text}",
        input_variables=variables
    )
    
    # Check input variables match
    input_vars = chain.prompt.input_variables
    
    assert set(input_vars) == set(variables)
    
    print("✓ Custom chain respects specified input variables")


def test_service_has_required_methods():
    """Test that service has all required methods"""
    
    service = get_langchain_service()
    
    # Check methods exist
    assert hasattr(service, 'create_conversation_chain')
    assert hasattr(service, 'create_qa_chain')
    assert hasattr(service, 'create_custom_chain')
    assert hasattr(service, 'simple_invoke')
    assert hasattr(service, 'chat_with_history')
    
    # Check they're callable
    assert callable(service.create_conversation_chain)
    assert callable(service.create_qa_chain)
    assert callable(service.create_custom_chain)
    assert callable(service.simple_invoke)
    assert callable(service.chat_with_history)
    
    print("✓ LangChain service has all required methods")


def test_llm_configuration():
    """Test that LLM is configured with correct settings"""
    
    from app.core.config import settings
    service = get_langchain_service()
    
    # Check LLM has expected configuration
    assert service.llm.model_name == settings.OPENAI_MODEL
    assert service.llm.temperature == settings.OPENAI_TEMPERATURE
    assert service.llm.max_tokens == settings.OPENAI_MAX_TOKENS
    
    print(f"✓ LLM configured: {settings.OPENAI_MODEL}, temp={settings.OPENAI_TEMPERATURE}")