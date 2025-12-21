"""Tests for LLM service ticket summarization."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.llm_service import LLMService
from database.models import Message, SenderRole
from datetime import datetime
from core.config import settings


@pytest.fixture
def mock_messages():
    """Create mock message objects for testing."""
    messages = [
        Message(
            id=1,
            ticket_id=1,
            sender_role=SenderRole.USER,
            text="Не могу войти в личный кабинет",
            created_at=datetime.now()
        ),
        Message(
            id=2,
            ticket_id=1,
            sender_role=SenderRole.ADMIN,
            text="Попробуйте сбросить пароль через форму восстановления",
            created_at=datetime.now()
        ),
        Message(
            id=3,
            ticket_id=1,
            sender_role=SenderRole.USER,
            text="Спасибо, помогло!",
            created_at=datetime.now()
        ),
    ]
    return messages


def test_format_dialogue(mock_messages):
    """Test dialogue formatting from Message objects."""
    result = LLMService.format_dialogue(mock_messages)
    
    assert "Студент: Не могу войти в личный кабинет" in result
    assert "Поддержка: Попробуйте сбросить пароль через форму восстановления" in result
    assert "Студент: Спасибо, помогло!" in result
    
    # Check that messages are on separate lines
    lines = result.split("\n")
    assert len(lines) == 3


def test_format_dialogue_empty():
    """Test dialogue formatting with empty message list."""
    result = LLMService.format_dialogue([])
    assert result == ""


@pytest.mark.asyncio
async def test_generate_summary_no_api_key():
    """Test summary generation when API key is not set."""
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = ""
        
        result = await LLMService.generate_summary("Test dialogue")
        
        assert result == "Резюме недоступно (нет ключа API)."


@pytest.mark.asyncio
async def test_generate_summary_success():
    """Test successful summary generation."""
    mock_response_data = {
        'choices': [
            {
                'message': {
                    'content': 'Студент не мог войти в личный кабинет. Проблема решена сбросом пароля.'
                }
            }
        ]
    }
    
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Create mock session
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary("Test dialogue")
            
            assert result == "Студент не мог войти в личный кабинет. Проблема решена сбросом пароля."
            
            # Verify API was called with correct parameters
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[0][0] == LLMService.BASE_URL
            assert call_args[1]['headers']['Authorization'] == "Bearer test-key"
            assert 'json' in call_args[1]
            payload = call_args[1]['json']
            assert payload['model'] == LLMService.MODEL
            assert payload['temperature'] == 0.3
            assert payload['max_tokens'] == 200


@pytest.mark.asyncio
async def test_generate_summary_api_error():
    """Test summary generation when API returns an error."""
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Create mock session
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary("Test dialogue")
            
            assert result == "Ошибка генерации резюме."


@pytest.mark.asyncio
async def test_generate_summary_connection_error():
    """Test summary generation when connection fails."""
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock session that raises exception
            mock_session = MagicMock()
            mock_session.post = MagicMock(side_effect=Exception("Connection error"))
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary("Test dialogue")
            
            assert result == "Ошибка соединения с ИИ."


@pytest.mark.asyncio
async def test_generate_summary_with_special_characters():
    """Test summary generation with special characters in dialogue."""
    dialogue_with_special_chars = "Студент: Проблема с <script>alert('test')</script>\nПоддержка: Решено"
    
    mock_response_data = {
        'choices': [
            {
                'message': {
                    'content': 'Проблема со скриптом. Решена.'
                }
            }
        ]
    }
    
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Create mock session
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary(dialogue_with_special_chars)
            
            assert result == "Проблема со скриптом. Решена."


@pytest.mark.asyncio
async def test_generate_summary_unexpected_response_format():
    """Test summary generation when API returns unexpected response format."""
    # Response without 'choices' key
    mock_response_data = {
        'error': {
            'message': 'Invalid model'
        }
    }
    
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Create mock session
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary("Test dialogue")
            
            assert result == "Ошибка формата ответа ИИ."


@pytest.mark.asyncio
async def test_generate_summary_empty_choices():
    """Test summary generation when API returns empty choices array."""
    mock_response_data = {
        'choices': []
    }
    
    with patch("services.llm_service.settings") as mock_settings:
        mock_settings.OPENROUTER_API_KEY = "test-key"
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Create mock session
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            result = await LLMService.generate_summary("Test dialogue")
            
            assert result == "Ошибка формата ответа ИИ."


def test_llm_model_name_from_settings():
    """Test that LLM model name is loaded from settings."""
    # The MODEL attribute should be set from settings
    assert LLMService.MODEL == settings.LLM_MODEL_NAME
    # Verify default value is as expected
    assert settings.LLM_MODEL_NAME == "google/gemini-3-flash-preview"

