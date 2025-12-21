import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser, Chat
from database.models import User, Ticket, TicketStatus, Category
from handlers.telegram import cmd_start, select_cat, handle_text, TicketForm
from core.config import settings

@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Configure execute to return a MagicMock (Result object)
    # The Result object's scalar_one_or_none should be a standard method (not async)
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
async def test_cmd_start(mock_state):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.first_name = "TestUser"
    message.answer = AsyncMock()

    await cmd_start(message, mock_state)

    mock_state.clear.assert_called_once()
    message.answer.assert_called_once()
    assert "Привет, TestUser" in message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_select_cat_active_ticket(mock_session, mock_state):
    # Mock active ticket check via patch because it's a helper function
    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket:
        # User has an active ticket
        mock_ticket = MagicMock()
        mock_ticket.daily_id = 123
        mock_get_active_ticket.return_value = mock_ticket

        # We need to configure the side_effect on the scalar_one_or_none method of the returned Result
        # get_active_ticket calls session.execute ONCE.
        # So we should return the Ticket object directly (which contains the user via relationship if needed, though mocked here)
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [
            Ticket(id=1, daily_id=100, user_id=1, status=TicketStatus.NEW) # Active ticket found
        ]

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.answer = AsyncMock()
        
        mock_bot = AsyncMock()

        await select_cat(callback, mock_state, mock_session, mock_bot)

        # Updated assertion for UX improvement
        args, kwargs = callback.answer.call_args
        assert "⚠️ У вас уже есть активная заявка" in args[0]
        assert "Просто напишите сообщение в чат" in args[0]
        assert kwargs['show_alert'] is True

        mock_state.set_state.assert_not_called()

@pytest.mark.asyncio
async def test_select_cat_no_active_ticket(mock_session, mock_state):
    # Mock active ticket check
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        None # No active ticket
    ]

    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket:
        mock_get_active_ticket.return_value = None

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.data = "cat_study"
        callback.message = AsyncMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        
        mock_bot = AsyncMock()

        await select_cat(callback, mock_state, mock_session, mock_bot)

        mock_state.update_data.assert_called_with(category="Учеба")
        mock_state.set_state.assert_called_with(TicketForm.waiting_text)
        callback.message.edit_text.assert_called()

@pytest.mark.asyncio
async def test_handle_text_ignore_staff(mock_session, mock_state, mock_bot):
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = settings.TG_STAFF_CHAT_ID
    message.answer = AsyncMock()

    await handle_text(message, mock_state, mock_bot, mock_session)

    message.answer.assert_not_called()

@pytest.mark.asyncio
async def test_handle_text_active_ticket_add_message(mock_session, mock_state, mock_bot):
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 12345
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123
    message.text = "Additional info"
    message.from_user.full_name = "User"
    message.answer = AsyncMock()

    with patch("handlers.telegram.FAQService") as MockFAQService, \
         patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket, \
         patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_message:

        MockFAQService.find_match.return_value = None

        # User has active ticket
        mock_ticket = MagicMock()
        mock_get_active_ticket.return_value = mock_ticket

        await handle_text(message, mock_state, mock_bot, mock_session)

        mock_add_message.assert_called_once()
        message.answer.assert_called_with("✅ Сообщение добавлено к диалогу.")
        mock_state.clear.assert_called()
        MockFAQService.find_match.assert_called_once_with("Additional info")

@pytest.mark.asyncio
async def test_handle_text_create_ticket_success_message(mock_session, mock_state, mock_bot):
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 12345
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123
    message.text = "My question"
    message.from_user.full_name = "User"
    message.answer = AsyncMock()

    mock_state.get_state.return_value = TicketForm.waiting_text
    mock_state.get_data.return_value = {"category": "Учеба"}

    with patch("handlers.telegram.FAQService") as MockFAQService, \
         patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active_ticket, \
         patch("handlers.telegram.create_ticket", new_callable=AsyncMock) as mock_create_ticket:

        MockFAQService.find_match.return_value = None
        mock_get_active_ticket.return_value = None

        # Mock created ticket
        ticket = MagicMock()
        ticket.daily_id = 999
        mock_create_ticket.return_value = ticket

        await handle_text(message, mock_state, mock_bot, mock_session)

        # Check that the success message is called and contains expected info
        args, kwargs = message.answer.call_args

        assert "✅ <b>Заявка #999 принята!</b>" in args[0]
        assert "Оператор ответит в рабочее время" in args[0]
