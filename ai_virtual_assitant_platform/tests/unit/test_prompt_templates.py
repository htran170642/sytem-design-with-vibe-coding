"""
Tests for Prompt Templates
"""

import pytest

from app.services.prompt_templates import (
    PromptTemplate,
    PromptTemplateManager,
    PromptRole,
    build_conversation_messages,
    format_context_for_rag,
)


def test_prompt_template_format_user_message():
    """Test formatting user message with placeholders"""
    
    template = PromptTemplate(
        name="test",
        system_message="You are helpful",
        user_template="Question: {question}\nContext: {context}",
    )
    
    result = template.format_user_message(
        question="What is AI?",
        context="AI stands for Artificial Intelligence"
    )
    
    assert "What is AI?" in result
    assert "AI stands for Artificial Intelligence" in result
    print("✓ Template formats user message correctly")


def test_prompt_template_missing_placeholder():
    """Test that missing placeholder raises error"""
    
    template = PromptTemplate(
        name="test",
        system_message="",
        user_template="Question: {question}",
    )
    
    with pytest.raises(ValueError, match="Missing required placeholder"):
        template.format_user_message()  # Missing 'question'
    
    print("✓ Missing placeholder raises ValueError")


def test_prompt_template_build_messages():
    """Test building complete message list"""
    
    template = PromptTemplate(
        name="test",
        system_message="You are a helpful assistant",
        user_template="Question: {question}",
    )
    
    messages = template.build_messages(question="What is Python?")
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant"
    assert messages[1]["role"] == "user"
    assert "What is Python?" in messages[1]["content"]
    
    print("✓ Builds correct message structure")


def test_prompt_template_no_system_message():
    """Test template without system message"""
    
    template = PromptTemplate(
        name="test",
        system_message="",
        user_template="{message}",
    )
    
    messages = template.build_messages(message="Hello")
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    
    print("✓ Works without system message")


def test_prompt_template_manager_get_template():
    """Test getting predefined templates"""
    
    template = PromptTemplateManager.get_template("general_chat")
    
    assert template.name == "general_chat"
    assert template.system_message != ""
    assert "{message}" in template.user_template
    
    print("✓ Gets predefined template")


def test_prompt_template_manager_list_templates():
    """Test listing all templates"""
    
    templates = PromptTemplateManager.list_templates()
    
    assert "general_chat" in templates
    assert "qa_with_context" in templates
    assert "summarization" in templates
    assert "code_generation" in templates
    
    print(f"✓ Lists {len(templates)} templates")


def test_prompt_template_manager_invalid_template():
    """Test getting non-existent template"""
    
    with pytest.raises(ValueError, match="not found"):
        PromptTemplateManager.get_template("nonexistent")
    
    print("✓ Raises error for invalid template name")


def test_qa_with_context_template():
    """Test QA with context template"""
    
    template = PromptTemplateManager.get_template("qa_with_context")
    
    messages = template.build_messages(
        question="What is machine learning?",
        context="Machine learning is a subset of AI that learns from data."
    )
    
    assert len(messages) == 2
    user_msg = messages[1]["content"]
    assert "What is machine learning?" in user_msg
    assert "Machine learning is a subset" in user_msg
    
    print("✓ QA with context template works correctly")


def test_code_generation_template():
    """Test code generation template"""
    
    template = PromptTemplateManager.get_template("code_generation")
    
    messages = template.build_messages(
        language="Python",
        task="Create a function to calculate fibonacci numbers"
    )
    
    assert len(messages) == 2
    user_msg = messages[1]["content"]
    assert "Python" in user_msg
    assert "fibonacci" in user_msg
    
    print("✓ Code generation template works correctly")


def test_add_custom_template():
    """Test adding custom template"""
    
    custom = PromptTemplate(
        name="custom_test",
        system_message="Custom system",
        user_template="Custom: {input}",
    )
    
    PromptTemplateManager.add_custom_template(custom)
    
    retrieved = PromptTemplateManager.get_template("custom_test")
    assert retrieved.name == "custom_test"
    
    print("✓ Can add custom templates")


def test_build_conversation_messages():
    """Test building conversation with system message"""
    
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    
    messages = build_conversation_messages(
        messages=history,
        system_message="You are helpful"
    )
    
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "assistant"
    
    print("✓ Builds conversation with system message")


def test_build_conversation_messages_no_system():
    """Test building conversation without system message"""
    
    history = [
        {"role": "user", "content": "Hello"},
    ]
    
    messages = build_conversation_messages(messages=history)
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    
    print("✓ Builds conversation without system message")


def test_format_context_for_rag():
    """Test formatting multiple contexts for RAG"""
    
    contexts = [
        "AI is artificial intelligence",
        "Machine learning is a subset of AI",
        "Deep learning uses neural networks",
    ]
    
    formatted = format_context_for_rag(contexts)
    
    assert "[Context 1]" in formatted
    assert "[Context 2]" in formatted
    assert "[Context 3]" in formatted
    assert "AI is artificial intelligence" in formatted
    assert "---" in formatted  # Separator
    
    print("✓ Formats contexts with numbering and separators")


def test_format_context_for_rag_max_limit():
    """Test context limiting"""
    
    contexts = [f"Context {i}" for i in range(10)]
    
    formatted = format_context_for_rag(contexts, max_contexts=3)
    
    assert "[Context 1]" in formatted
    assert "[Context 2]" in formatted
    assert "[Context 3]" in formatted
    assert "[Context 4]" not in formatted
    
    print("✓ Limits contexts to max_contexts parameter")


def test_format_context_for_rag_custom_separator():
    """Test custom separator"""
    
    contexts = ["Context 1", "Context 2"]
    
    formatted = format_context_for_rag(contexts, separator="\n\n***\n\n")
    
    assert "***" in formatted
    assert "---" not in formatted
    
    print("✓ Uses custom separator")