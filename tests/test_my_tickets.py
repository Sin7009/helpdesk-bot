"""Tests for 'My Tickets' feature."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser, Chat
from database.models import User, Ticket, TicketStatus, Category, SourceType
from handlers.telegram import show_my_tickets, show_ticket_detail, add_comment_ask, process_comment, CommentForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_session():
    session = AsyncMock()
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    session.commit = AsyncMock()
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


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.external_id = 123
    user.source = SourceType.TELEGRAM
    user.full_name = "Test User"
    return user


@pytest.fixture
def mock_category():
    category = MagicMock(spec=Category)
    category.id = 1
    category.name = "IT Support"
    return category


@pytest.fixture
def mock_ticket(mock_user, mock_category):
    ticket = MagicMock(spec=Ticket)
    ticket.id = 1
    ticket.daily_id = 100
    ticket.user_id = 1
    ticket.status = TicketStatus.NEW
    ticket.question_text = "Test question"
    ticket.summary = None
    ticket.created_at = datetime(2025, 12, 22, 10, 0, 0)
    ticket.user = mock_user
    ticket.category = mock_category
    return ticket


@pytest.mark.asyncio
async def test_show_my_tickets_no_user(mock_session):
    """Test show_my_tickets when user doesn't exist."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()

    # Mock no user found
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    await show_my_tickets(callback, mock_session)

    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert "У вас пока нет заявок" in args[0]


@pytest.mark.asyncio
async def test_show_my_tickets_empty_list(mock_session, mock_user):
    """Test show_my_tickets when user has no tickets."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()

    # Mock user found but no tickets
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_user]
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    await show_my_tickets(callback, mock_session)

    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert "Список заявок пуст" in args[0]


@pytest.mark.asyncio
async def test_show_my_tickets_with_tickets(mock_session, mock_user, mock_ticket):
    """Test show_my_tickets with tickets in list."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()

    # Mock user found with tickets
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_user]
    mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_ticket]

    await show_my_tickets(callback, mock_session)

    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert "Мои заявки" in args[0]
    assert kwargs.get('parse_mode') == 'HTML'


@pytest.mark.asyncio
async def test_show_ticket_detail_not_owner(mock_session, mock_user, mock_ticket, mock_state):
    """Test show_ticket_detail when user doesn't own the ticket."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 456  # Different user
    callback.data = "ticket_detail_1"
    callback.answer = AsyncMock()

    # Create a different user who is not the owner
    different_user = MagicMock(spec=User)
    different_user.id = 999
    different_user.external_id = 456

    # Mock ticket and user lookups
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        different_user  # But different user
    ]

    await show_ticket_detail(callback, mock_session, mock_state)

    callback.answer.assert_called_once()
    args = callback.answer.call_args[0]
    assert "Это не ваша заявка" in args[0]


@pytest.mark.asyncio
async def test_show_ticket_detail_success(mock_session, mock_user, mock_ticket, mock_state):
    """Test show_ticket_detail successfully displays ticket."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.data = "ticket_detail_1"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()

    # Mock ticket and user lookups - user owns the ticket
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        mock_user  # Owner found
    ]

    await show_ticket_detail(callback, mock_session, mock_state)

    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert f"Заявка #{mock_ticket.daily_id}" in args[0]
    assert mock_ticket.question_text in args[0] or "Test question" in args[0]  # HTML escaped version
    assert kwargs.get('parse_mode') == 'HTML'


@pytest.mark.asyncio
async def test_add_comment_ask_not_owner(mock_session, mock_user, mock_ticket, mock_state):
    """Test add_comment_ask when user doesn't own the ticket."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 456
    callback.data = "add_comment_1"
    callback.answer = AsyncMock()

    # Create a different user
    different_user = MagicMock(spec=User)
    different_user.id = 999
    different_user.external_id = 456

    # Mock ticket and user lookups
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        different_user  # But different user
    ]

    await add_comment_ask(callback, mock_state, mock_session)

    callback.answer.assert_called_once()
    args, kwargs = callback.answer.call_args
    assert "Ошибка доступа" in args[0]
    assert kwargs.get('show_alert') is True


@pytest.mark.asyncio
async def test_add_comment_ask_success(mock_session, mock_user, mock_ticket, mock_state):
    """Test add_comment_ask successfully initiates comment flow."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = 123
    callback.data = "add_comment_1"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()

    # Mock ticket and user lookups - user owns the ticket
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        mock_user  # Owner found
    ]

    await add_comment_ask(callback, mock_state, mock_session)

    mock_state.update_data.assert_called_once_with(comment_ticket_id=1)
    mock_state.set_state.assert_called_once_with(CommentForm.waiting_comment)
    callback.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_process_comment_no_ticket_id(mock_session, mock_state, mock_bot):
    """Test process_comment when no ticket_id in state."""
    message = AsyncMock(spec=Message)
    message.text = "Test comment"
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123

    # Mock empty state
    mock_state.get_data.return_value = {}

    await process_comment(message, mock_state, mock_session, mock_bot)

    message.answer.assert_called_once()
    args = message.answer.call_args[0]
    assert "Ошибка состояния" in args[0]
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_process_comment_not_owner(mock_session, mock_user, mock_ticket, mock_state, mock_bot):
    """Test process_comment when user doesn't own the ticket."""
    message = AsyncMock(spec=Message)
    message.text = "Test comment"
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 456
    message.photo = None
    message.document = None
    message.caption = None

    # Mock state with ticket_id
    mock_state.get_data.return_value = {"comment_ticket_id": 1}

    # Create a different user
    different_user = MagicMock(spec=User)
    different_user.id = 999
    different_user.external_id = 456

    # Mock ticket and user lookups
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        different_user  # But different user
    ]

    await process_comment(message, mock_state, mock_session, mock_bot)

    message.answer.assert_called_once()
    args = message.answer.call_args[0]
    assert "Ошибка доступа" in args[0]
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_process_comment_success_text(mock_session, mock_user, mock_ticket, mock_state, mock_bot):
    """Test process_comment successfully adds text comment."""
    message = AsyncMock(spec=Message)
    message.text = "Test comment"
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123
    message.photo = None
    message.document = None
    message.caption = None

    # Mock state with ticket_id
    mock_state.get_data.return_value = {"comment_ticket_id": 1}

    # Mock ticket and user lookups - user owns the ticket
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,  # Ticket found
        mock_user  # Owner found
    ]

    with patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg:
        await process_comment(message, mock_state, mock_session, mock_bot)

        mock_add_msg.assert_called_once()
        args, kwargs = mock_add_msg.call_args
        assert args[0] == mock_session
        assert args[1] == mock_ticket
        assert args[2] == "Test comment"
        assert args[3] == mock_bot
        assert kwargs.get('media_id') is None
        assert kwargs.get('content_type') == "text"

        message.answer.assert_called_once()
        assert "Комментарий добавлен" in message.answer.call_args[0][0]
        mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_process_comment_with_photo(mock_session, mock_user, mock_ticket, mock_state, mock_bot):
    """Test process_comment with photo attachment."""
    message = AsyncMock(spec=Message)
    message.text = None
    message.caption = "Photo caption"
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123
    message.document = None

    # Mock photo
    photo = MagicMock()
    photo.file_id = "photo_file_id_123"
    message.photo = [photo]

    # Mock state with ticket_id
    mock_state.get_data.return_value = {"comment_ticket_id": 1}

    # Mock ticket and user lookups
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,
        mock_user
    ]

    with patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg:
        await process_comment(message, mock_state, mock_session, mock_bot)

        mock_add_msg.assert_called_once()
        args, kwargs = mock_add_msg.call_args
        assert kwargs.get('media_id') == "photo_file_id_123"
        assert kwargs.get('content_type') == "photo"


@pytest.mark.asyncio
async def test_process_comment_media_without_file_id(mock_session, mock_user, mock_ticket, mock_state, mock_bot):
    """Test process_comment validation when media_id is missing."""
    message = AsyncMock(spec=Message)
    message.text = None
    message.caption = None
    message.answer = AsyncMock()
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = 123

    # Mock photo but with no file_id (edge case)
    photo = MagicMock()
    photo.file_id = None
    message.photo = [photo]
    message.document = None

    # Mock state with ticket_id
    mock_state.get_data.return_value = {"comment_ticket_id": 1}

    # Mock ticket and user lookups
    mock_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ticket,
        mock_user
    ]

    await process_comment(message, mock_state, mock_session, mock_bot)

    message.answer.assert_called_once()
    args = message.answer.call_args[0]
    assert "не удалось получить файл" in args[0]
    mock_state.clear.assert_called_once()
