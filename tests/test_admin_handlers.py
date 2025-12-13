import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User as TgUser
from aiogram.filters import CommandObject
from database.models import User, Ticket, TicketStatus
from handlers.admin import admin_reply_command, admin_close_ticket, add_category_cmd
from core.config import settings

@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Configure session to work as context manager
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session

@pytest.mark.asyncio
async def test_admin_reply_command_no_args(mock_session, mock_bot):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()
    command = CommandObject(prefix="/", command="reply", args=None)

    # Patch new_session to return our mock session
    with patch("handlers.admin.new_session", return_value=mock_session):
        await admin_reply_command(message, command, mock_bot)

    message.answer.assert_called_with("Формат: /reply ID Текст")

@pytest.mark.asyncio
async def test_admin_close_ticket_not_found(mock_session, mock_bot):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()
    command = CommandObject(prefix="/", command="close", args="999")

    # Mock DB: User check (Admin), Ticket check (None)
    mock_session.execute.side_effect = [
        # is_admin_or_mod is skipped if user == TG_ADMIN_ID
        # Ticket query
        MagicMock(scalar_one_or_none=lambda: None)
    ]

    with patch("handlers.admin.new_session", return_value=mock_session):
        await admin_close_ticket(message, command, mock_bot, mock_session)

    message.answer.assert_called_with("Тикет не найден или уже закрыт.")

@pytest.mark.asyncio
async def test_add_category_no_args(mock_session):
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = settings.TG_ADMIN_ID
    message.answer = AsyncMock()
    command = CommandObject(prefix="/", command="add_category", args=None)

    with patch("handlers.admin.new_session", return_value=mock_session):
        await add_category_cmd(message, command)

    message.answer.assert_called_with("Ошибка: введите название категории")
