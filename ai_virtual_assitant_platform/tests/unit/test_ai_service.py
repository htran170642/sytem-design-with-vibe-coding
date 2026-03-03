"""
Tests for AI Service — signatures + mocked LLM responses.
Phase 8, Step 3: Mock LLM responses for tests.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.services.ai_service as ai_module
import app.services.openai_client as oc_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_response(content: str, model: str = "gpt-4o-mini") -> MagicMock:
    """Build a minimal mock that mimics openai.ChatCompletion response."""
    response = MagicMock()
    response.model = model
    response.choices[0].message.content = content
    response.choices[0].finish_reason = "stop"
    response.usage.prompt_tokens = 20
    response.usage.completion_tokens = 10
    response.usage.total_tokens = 30
    return response


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the AIService singleton before and after each test."""
    original = ai_module._ai_service
    ai_module._ai_service = None
    yield
    ai_module._ai_service = original


@pytest.fixture()
def mock_openai_client():
    """
    Patch the AsyncOpenAI client so no real HTTP calls are made.
    Returns the mock of client.chat.completions.create.
    """
    with patch("app.services.openai_client.AsyncOpenAI") as mock_cls:
        inner_client = MagicMock()
        mock_cls.return_value = inner_client
        # Also reset the openai_client singleton
        original_oc = oc_module._client
        oc_module._client = None
        yield inner_client
        oc_module._client = original_oc


# ---------------------------------------------------------------------------
# Existing signature / structure tests (unchanged)
# ---------------------------------------------------------------------------

def test_ai_service_singleton():
    """Test that get_ai_service returns same instance."""
    from app.services.ai_service import get_ai_service

    s1 = get_ai_service()
    s2 = get_ai_service()
    assert s1 is s2
    print("✓ AI service is a singleton")


def test_ai_service_initialization():
    """Test AI service initializes correctly."""
    from app.services.ai_service import get_ai_service

    service = get_ai_service()
    assert service.client is not None
    assert service.template_manager is not None
    print("✓ AI service initializes with client and template manager")


def test_ai_service_has_required_methods():
    """Test that AI service has all required methods."""
    from app.services.ai_service import get_ai_service

    service = get_ai_service()
    for name in ("chat_completion", "simple_chat", "qa_with_context", "conversation", "stream_chat_completion"):
        assert hasattr(service, name) and callable(getattr(service, name))
    print("✓ AI service has all required methods")


def test_simple_chat_signature():
    """Test simple_chat has correct parameters."""
    import inspect
    from app.services.ai_service import get_ai_service

    sig = inspect.signature(get_ai_service().simple_chat)
    params = list(sig.parameters)
    assert "message" in params
    assert "system_message" in params
    assert "temperature" in params
    assert "max_tokens" in params
    print("✓ simple_chat has correct signature")


def test_qa_with_context_signature():
    """Test qa_with_context has correct parameters."""
    import inspect
    from app.services.ai_service import get_ai_service

    sig = inspect.signature(get_ai_service().qa_with_context)
    params = list(sig.parameters)
    assert "question" in params
    assert "context" in params
    assert "temperature" in params
    assert "max_tokens" in params
    print("✓ qa_with_context has correct signature")


def test_conversation_signature():
    """Test conversation has correct parameters."""
    import inspect
    from app.services.ai_service import get_ai_service

    sig = inspect.signature(get_ai_service().conversation)
    params = list(sig.parameters)
    assert "message" in params
    assert "history" in params
    assert "system_message" in params
    assert "temperature" in params
    assert "max_tokens" in params
    print("✓ conversation has correct signature")


def test_chat_completion_signature():
    """Test chat_completion has correct parameters."""
    import inspect
    from app.services.ai_service import get_ai_service

    sig = inspect.signature(get_ai_service().chat_completion)
    params = list(sig.parameters)
    assert "messages" in params
    assert "temperature" in params
    assert "max_tokens" in params
    assert "model" in params
    print("✓ chat_completion has correct signature")


def test_service_uses_templates():
    """Test that service can access prompt templates."""
    from app.services.ai_service import get_ai_service

    service = get_ai_service()
    templates = service.template_manager.list_templates()
    assert len(templates) > 0
    assert "general_chat" in templates
    assert "qa_with_context" in templates
    assert "conversation_with_history" in templates
    print(f"✓ Service has access to {len(templates)} templates")


# ---------------------------------------------------------------------------
# Mocked LLM behaviour tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_completion_returns_correct_structure(mock_openai_client):
    """chat_completion returns dict with expected keys."""
    from app.services.ai_service import get_ai_service

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response("Hello from AI")
    )

    service = get_ai_service()
    result = await service.chat_completion(
        messages=[{"role": "user", "content": "Hi"}]
    )

    assert result["message"] == "Hello from AI"
    assert "model" in result
    assert "finish_reason" in result
    assert result["finish_reason"] == "stop"
    assert "usage" in result
    assert result["usage"]["total_tokens"] == 30
    print("✓ chat_completion returns correct structure with mocked response")


@pytest.mark.asyncio
async def test_chat_completion_passes_messages_to_api(mock_openai_client):
    """chat_completion forwards messages to the OpenAI API."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("pong"))
    mock_openai_client.chat.completions.create = create_mock

    messages = [{"role": "user", "content": "ping"}]
    service = get_ai_service()
    await service.chat_completion(messages=messages)

    _, kwargs = create_mock.call_args
    assert kwargs["messages"] == messages
    print("✓ chat_completion passes messages through to OpenAI API")


@pytest.mark.asyncio
async def test_chat_completion_raises_llm_error_on_openai_error(mock_openai_client):
    """chat_completion wraps OpenAI errors as LLMError."""
    from openai import OpenAIError
    from app.services.ai_service import get_ai_service
    from app.core.exceptions import LLMError

    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=OpenAIError("API quota exceeded")
    )

    service = get_ai_service()
    with pytest.raises(LLMError):
        await service.chat_completion(
            messages=[{"role": "user", "content": "test"}]
        )
    print("✓ OpenAI errors are wrapped as LLMError")


@pytest.mark.asyncio
async def test_simple_chat_returns_string(mock_openai_client):
    """simple_chat returns the message string directly."""
    from app.services.ai_service import get_ai_service

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response("I am fine, thanks!")
    )

    service = get_ai_service()
    result = await service.simple_chat("How are you?")

    assert isinstance(result, str)
    assert result == "I am fine, thanks!"
    print("✓ simple_chat returns plain string from LLM")


@pytest.mark.asyncio
async def test_simple_chat_uses_custom_system_message(mock_openai_client):
    """simple_chat includes custom system message when provided."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("reply"))
    mock_openai_client.chat.completions.create = create_mock

    service = get_ai_service()
    await service.simple_chat("Hello", system_message="You are a pirate.")

    _, kwargs = create_mock.call_args
    system_msgs = [m for m in kwargs["messages"] if m["role"] == "system"]
    assert any("pirate" in m["content"] for m in system_msgs)
    print("✓ simple_chat uses custom system message")


@pytest.mark.asyncio
async def test_simple_chat_uses_default_template_when_no_system_message(mock_openai_client):
    """simple_chat uses the general_chat template when no system message given."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("reply"))
    mock_openai_client.chat.completions.create = create_mock

    service = get_ai_service()
    await service.simple_chat("Hello")

    _, kwargs = create_mock.call_args
    # Template provides a system message containing "AIVA"
    system_msgs = [m for m in kwargs["messages"] if m["role"] == "system"]
    assert len(system_msgs) == 1
    assert "AIVA" in system_msgs[0]["content"]
    print("✓ simple_chat uses AIVA template when no system message given")


@pytest.mark.asyncio
async def test_qa_with_context_includes_question_and_context(mock_openai_client):
    """qa_with_context builds messages with both question and context."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("answer"))
    mock_openai_client.chat.completions.create = create_mock

    service = get_ai_service()
    await service.qa_with_context(
        question="What is Python?",
        context="Python is a programming language.",
    )

    _, kwargs = create_mock.call_args
    user_msg = next(m for m in kwargs["messages"] if m["role"] == "user")
    assert "What is Python?" in user_msg["content"]
    assert "Python is a programming language." in user_msg["content"]
    print("✓ qa_with_context includes question and context in prompt")


@pytest.mark.asyncio
async def test_qa_with_context_uses_low_temperature(mock_openai_client):
    """qa_with_context uses temperature 0.3 for factual accuracy."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("answer"))
    mock_openai_client.chat.completions.create = create_mock

    service = get_ai_service()
    await service.qa_with_context(question="Q?", context="C")

    _, kwargs = create_mock.call_args
    assert kwargs["temperature"] == 0.3
    print("✓ qa_with_context uses temperature=0.3")


@pytest.mark.asyncio
async def test_conversation_includes_history(mock_openai_client):
    """conversation appends history and new message before calling API."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("I remember!"))
    mock_openai_client.chat.completions.create = create_mock

    history = [
        {"role": "user", "content": "I am Alice"},
        {"role": "assistant", "content": "Hello Alice!"},
    ]
    service = get_ai_service()
    await service.conversation(message="What's my name?", history=history)

    _, kwargs = create_mock.call_args
    messages = kwargs["messages"]
    # History is included
    assert any("Alice" in m["content"] for m in messages)
    # New question is included
    assert any("What's my name?" in m["content"] for m in messages)
    print("✓ conversation includes full history in messages")


@pytest.mark.asyncio
async def test_conversation_with_custom_system_message(mock_openai_client):
    """conversation uses custom system message when provided."""
    from app.services.ai_service import get_ai_service

    create_mock = AsyncMock(return_value=_make_openai_response("arr!"))
    mock_openai_client.chat.completions.create = create_mock

    service = get_ai_service()
    await service.conversation(
        message="Hello",
        history=[],
        system_message="You are a pirate.",
    )

    _, kwargs = create_mock.call_args
    system_msgs = [m for m in kwargs["messages"] if m["role"] == "system"]
    assert any("pirate" in m["content"] for m in system_msgs)
    print("✓ conversation respects custom system message")


def test_get_usage_stats_returns_dict():
    """get_usage_stats delegates to token_tracker and returns a dict."""
    from app.services.ai_service import get_ai_service

    service = get_ai_service()
    stats = service.get_usage_stats()

    assert isinstance(stats, dict)
    print("✓ get_usage_stats returns a dict")


def test_reset_usage_stats_works():
    """reset_usage_stats runs without errors."""
    from app.services.ai_service import get_ai_service

    service = get_ai_service()
    service.reset_usage_stats()   # Should not raise
    print("✓ reset_usage_stats executes without errors")
