
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser
from handlers.telegram import select_cat, handle_message_content, TicketForm
from database.models import SourceType

@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot

@pytest.fixture
def mock_session():
    session = AsyncMock()
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    return session

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state

@pytest.mark.asyncio
async def test_handle_text_saves_unsolicited_text(mock_session, mock_state, mock_bot):
    message = AsyncMock(spec=Message)
    # Correctly mock chat object
    message.chat = MagicMock()
    message.chat.id = 12345
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123
    message.text = "Unsolicited question"
    message.photo = None
    message.document = None
    message.answer = AsyncMock()

    # Mock no active ticket and no FAQ match
    with patch("handlers.telegram.FAQService") as MockFAQService, \
         patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket:

        MockFAQService.find_match.return_value = None
        mock_get_active_ticket.return_value = None
        mock_state.get_state.return_value = None

        await handle_message_content(message, mock_state, mock_bot, mock_session)

        # Verify text was saved
        mock_state.update_data.assert_called_with(saved_text="Unsolicited question")

        # Verify response message
        args, kwargs = message.answer.call_args
        assert "Я запомнил ваш вопрос" in args[0]
        assert "Теперь выберите тему" in args[0]

@pytest.mark.asyncio
async def test_select_cat_uses_saved_text(mock_session, mock_state, mock_bot):
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.from_user.full_name = "User Name"
    callback.data = "cat_study"
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()

    # Mock saved text in state
    mock_state.get_data.return_value = {"saved_text": "Saved question"}

    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket, \
         patch("handlers.telegram.create_ticket", new_callable=AsyncMock) as mock_create_ticket:

        mock_get_active_ticket.return_value = None

        mock_ticket = MagicMock()
        mock_ticket.daily_id = 101
        mock_create_ticket.return_value = mock_ticket

        await select_cat(callback, mock_state, mock_session, mock_bot)

        # Verify create_ticket called with saved text
        # Use SourceType.TELEGRAM for correct assertion
        mock_create_ticket.assert_called_with(
            mock_session, 123, SourceType.TELEGRAM, "Saved question", mock_bot, "Учеба", "User Name", media_id=None, content_type="text"
        )

        # Verify state cleared and success message shown
        mock_state.clear.assert_called_once()
        callback.message.edit_text.assert_called()
        args, kwargs = callback.message.edit_text.call_args
        assert "Заявка #101 принята" in args[0]
        assert "Учеба" in args[0]

@pytest.mark.asyncio
async def test_select_cat_no_saved_text(mock_session, mock_state, mock_bot):
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.data = "cat_study"
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()

    # Mock NO saved text
    mock_state.get_data.return_value = {}

    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket:
        mock_get_active_ticket.return_value = None

        await select_cat(callback, mock_state, mock_session, mock_bot)

        # Verify normal flow (ask for text)
        mock_state.update_data.assert_called_with(category="Учеба")
        mock_state.set_state.assert_called_with(TicketForm.waiting_text)

        args, kwargs = callback.message.edit_text.call_args
        assert "Напишите ваш вопрос" in args[0]
