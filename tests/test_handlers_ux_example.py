import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from handlers.telegram import show_example_ticket

@pytest.mark.asyncio
async def test_show_example_ticket():
    # Setup mocks
    callback = AsyncMock(spec=CallbackQuery)
    # Ensure message is an AsyncMock but also that its methods are AsyncMocks
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"category": "IT"}

    # Call handler
    await show_example_ticket(callback, state)

    # Verify interaction
    state.get_data.assert_called_once()

    # Verify message edit
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args

    text = args[0]
    assert "Тема: <b>IT</b>" in text
    assert "Пример хорошего обращения" in text
    assert "ivanov.i" in text

    assert kwargs['parse_mode'] == "HTML"
    assert kwargs['reply_markup'] is not None

    # Verify callback answer
    callback.answer.assert_called_once()
