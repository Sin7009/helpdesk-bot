import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.llm_service import LLMService
from database.models import Message

@pytest.mark.asyncio
async def test_generate_summary_success():
    """Test successful summary generation."""
    with patch('services.llm_service.settings') as mock_settings, \
         patch('services.llm_service.aiohttp.ClientSession') as mock_session_cls:
        # Mock settings to have API key
        mock_settings.OPENROUTER_API_KEY = "test_api_key"
        mock_settings.LLM_MODEL_NAME = "test-model"
        
        # Mock session must be a MagicMock that returns a context manager
        mock_session = MagicMock()
        mock_request_ctx = MagicMock()
        mock_response = AsyncMock()
        
        mock_response.status = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Generated summary'}}]
        }
        
        # Chain: ClientSession() -> session -> session.post() -> context -> response
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        summary = await LLMService.generate_summary("User: Problem\nAdmin: Solution")
        assert summary == "Generated summary"

@pytest.mark.asyncio
async def test_generate_summary_api_error():
    """Test API error handling."""
    with patch('services.llm_service.settings') as mock_settings, \
         patch('services.llm_service.aiohttp.ClientSession') as mock_session_cls:
        # Mock settings to have API key
        mock_settings.OPENROUTER_API_KEY = "test_api_key"
        mock_settings.LLM_MODEL_NAME = "test-model"
        
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"
        
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value = mock_response

        summary = await LLMService.generate_summary("User: Problem")
        assert summary == "Ошибка генерации резюме."

@pytest.mark.asyncio
async def test_suggest_faq_updates_success():
    """Test successful FAQ suggestion."""
    with patch('services.llm_service.settings') as mock_settings, \
         patch('services.llm_service.aiohttp.ClientSession') as mock_session_cls:
        # Mock settings to have API key
        mock_settings.OPENROUTER_API_KEY = "test_api_key"
        mock_settings.LLM_MODEL_NAME = "test-model"
        
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Analysis result'}}]
        }
        
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value = mock_response

        result = await LLMService.suggest_faq_updates(["Problem 1", "Problem 2"])
        assert result == "Analysis result"

@pytest.mark.asyncio
async def test_suggest_faq_updates_empty():
    """Test empty input."""
    result = await LLMService.suggest_faq_updates([])
    assert result == "Нет данных для анализа."

@pytest.mark.asyncio
async def test_suggest_faq_updates_error():
    """Test error handling in analysis."""
    with patch('services.llm_service.settings') as mock_settings, \
         patch('services.llm_service.aiohttp.ClientSession') as mock_session_cls:
        # Mock settings to have API key
        mock_settings.OPENROUTER_API_KEY = "test_api_key"
        mock_settings.LLM_MODEL_NAME = "test-model"
        
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Error"
        
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value = mock_response

        result = await LLMService.suggest_faq_updates(["Problem 1"])
        assert result == "Ошибка анализа FAQ."

def test_format_dialogue():
    """Test dialogue formatting."""
    messages = [
        Message(sender_role="user", text="Hello"),
        Message(sender_role="admin", text="Hi there"),
        Message(sender_role="user", text="I have a problem")
    ]
    formatted = LLMService.format_dialogue(messages)
    expected = "Студент: Hello\nПоддержка: Hi there\nСтудент: I have a problem"
    assert formatted == expected

def test_format_dialogue_empty():
    """Test empty dialogue formatting."""
    assert LLMService.format_dialogue([]) == ""
