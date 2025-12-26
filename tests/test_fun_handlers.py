
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User as TgUser
from handlers.telegram import handle_unsupported_content

@pytest.mark.asyncio
async def test_handle_unsupported_content_replies_with_humor():
    # Setup mock message
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()

    # Run handler
    await handle_unsupported_content(message)

    # Assert
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    response_text = args[0]

    # Check for keywords from the humorous text
    assert "Ого, какая штука!" in response_text
    assert "старомоден" in response_text
    assert "опишите словами" in response_text
