import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.filters import CommandObject
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat, ReactionTypeEmoji
from handlers.admin import (
    admin_reply_native,
    admin_reply_command,
    admin_close_ticket,
    close_ticket_btn,
    add_category_cmd,
    process_reply
)
from database.models import User, UserRole, Ticket, TicketStatus, Category, Message as DbMessage
from core.config import settings

@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(id=999) # Bot ID
    # Configure send_message to return a message with an integer message_id
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message
    return bot

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Mock session.execute result
    # Explicitly creating a MagicMock for the Result object to avoid AsyncMock children issues
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    # Mock session.add (sync)
    session.add = MagicMock()
    return session

@pytest.mark.asyncio
async def test_admin_reply_native_valid(mock_bot, mock_session):
    message = AsyncMock(spec=Message)
    # Manually attach from_user to avoid spec issues with nested mocks
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID

    message.reply_to_message = AsyncMock(spec=Message)
    message.reply_to_message.from_user = MagicMock(spec=TgUser)
    message.reply_to_message.from_user.id = 999 # From bot
    message.reply_to_message.text = "Question ID: #123"
    message.reply_to_message.message_id = 54321  # Add message_id attribute
    message.text = "Answer"

    # Mock ticket found
    ticket = MagicMock(spec=Ticket)
    ticket.id = 123
    ticket.status = TicketStatus.NEW
    ticket.user.external_id = 111

    # Configure the result_mock (which is mock_session.execute.return_value)
    mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

    with patch("handlers.admin.process_reply", new_callable=AsyncMock) as mock_process:
        await admin_reply_native(message, mock_bot, mock_session)

        # The actual call includes ticket_obj parameter
        mock_process.assert_called_with(mock_bot, mock_session, 123, "Answer", message, close=False, ticket_obj=ticket)

@pytest.mark.asyncio
async def test_admin_reply_native_ignore_user_reply(mock_bot, mock_session):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID

    message.reply_to_message = AsyncMock(spec=Message)
    message.reply_to_message.from_user = MagicMock(spec=TgUser)
    message.reply_to_message.from_user.id = 888 # Not bot

    await admin_reply_native(message, mock_bot, mock_session)
    # Should return early
    mock_session.execute.assert_not_called()

@pytest.mark.asyncio
async def test_admin_reply_command_valid(mock_bot):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()

    command = CommandObject(prefix="/", command="reply", args="123 Answer text")

    # Mock new_session context manager
    mock_session = AsyncMock()
    result_mock = MagicMock()
    mock_session.execute.return_value = result_mock
    result_mock.scalar_one_or_none.return_value = None

    with patch("handlers.admin.new_session", return_value=mock_session), \
         patch("handlers.admin.process_reply", new_callable=AsyncMock) as mock_process:

        # We need mock_session as context manager
        mock_session.__aenter__.return_value = mock_session

        await admin_reply_command(message, command, mock_bot)

        mock_process.assert_called_with(mock_bot, mock_session, 123, "Answer text", message, close=False)

@pytest.mark.asyncio
async def test_admin_close_ticket_valid(mock_bot):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()

    command = CommandObject(prefix="/", command="close", args="123")

    ticket = MagicMock(spec=Ticket)
    ticket.id = 123
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.user.external_id = 111

    mock_session = AsyncMock()
    result_mock = MagicMock()
    mock_session.execute.return_value = result_mock
    result_mock.scalar_one_or_none.return_value = ticket

    await admin_close_ticket(message, command, mock_bot, mock_session)

    assert ticket.status == TicketStatus.CLOSED
    mock_session.commit.assert_called()
    message.answer.assert_called_with("Тикет #123 закрыт.")

@pytest.mark.asyncio
async def test_close_ticket_btn_valid(mock_bot):
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = settings.TG_ADMIN_ID
    callback.data = "close_123"
    callback.message = AsyncMock()
    callback.message.text = "Sample ticket text"  # Set text as a regular property, not a coroutine
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    # Explicitly set text attribute for the message mock to be a string, not AsyncMock
    callback.message.text = "Ticket Content"
    callback.message.caption = None

    ticket = MagicMock(spec=Ticket)
    ticket.id = 123
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.user.external_id = 111

    mock_session = AsyncMock()
    result_mock = MagicMock()
    mock_session.execute.return_value = result_mock
    result_mock.scalar_one_or_none.return_value = ticket

    with patch("handlers.admin.new_session", return_value=mock_session):
        mock_session.__aenter__.return_value = mock_session

        await close_ticket_btn(callback, mock_bot)

        assert ticket.status == TicketStatus.CLOSED
        mock_session.commit.assert_called()
        callback.message.edit_text.assert_called()

@pytest.mark.asyncio
async def test_add_category_cmd_valid():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()

    command = CommandObject(prefix="/", command="add_category", args="NewCat")

    mock_session = AsyncMock()
    mock_session.add = MagicMock() # Sync

    with patch("handlers.admin.new_session", return_value=mock_session):
        mock_session.__aenter__.return_value = mock_session

        await add_category_cmd(message, command)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        args, _ = mock_session.add.call_args
        assert isinstance(args[0], Category)
        assert args[0].name == "NewCat"
        message.answer.assert_called_with("✅ Категория 'NewCat' добавлена.")

@pytest.mark.asyncio
async def test_add_category_cmd_no_args():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()

    command = CommandObject(prefix="/", command="add_category", args="")

    mock_session = AsyncMock()

    with patch("handlers.admin.new_session", return_value=mock_session):
        mock_session.__aenter__.return_value = mock_session

        await add_category_cmd(message, command)

        message.answer.assert_called_with("Ошибка: введите название категории")
        mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_process_reply_logic(mock_bot, mock_session):
    """Test the actual process_reply logic without mocking it."""
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()

    ticket = MagicMock(spec=Ticket)
    ticket.id = 123
    ticket.status = TicketStatus.NEW
    ticket.user.external_id = 111

    # Mock finding ticket
    mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

    await process_reply(mock_bot, mock_session, 123, "Answer", message, close=False)

    # Assertions
    mock_bot.send_message.assert_called_once()
    args, kwargs = mock_bot.send_message.call_args
    assert args[0] == 111 # User ID
    assert "Answer" in args[1]

    # Check status update
    assert ticket.status == TicketStatus.IN_PROGRESS

    # Check message added
    mock_session.add.assert_called_once()
    added_msg = mock_session.add.call_args[0][0]
    assert isinstance(added_msg, DbMessage)
    assert added_msg.text == "Answer"

    mock_session.commit.assert_called_once()
    message.react.assert_called_once()

@pytest.mark.asyncio
async def test_process_reply_close_ticket(mock_bot, mock_session):
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()

    ticket = MagicMock(spec=Ticket)
    ticket.id = 123
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.user.external_id = 111

    mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

    await process_reply(mock_bot, mock_session, 123, "Answer", message, close=True)

    assert ticket.status == TicketStatus.CLOSED
    mock_session.commit.assert_called_once()
