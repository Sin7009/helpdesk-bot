import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.ticket_service import TicketUpdateResult
from handlers import telegram
from database.models import Ticket, TicketStatus, SourceType, User

@pytest.mark.asyncio
async def test_gratitude_response(async_session, mock_bot):
    """Test that 'thanks' triggers GRATITUDE result and 'You're welcome' message."""

    # 1. Mock ticket (Closed)
    user = User(id=1, external_id=123, source=SourceType.TELEGRAM)
    ticket = Ticket(
        id=1,
        user_id=1,
        status=TicketStatus.CLOSED,
        daily_id=1,
        user=user
    )

    # Mock active ticket retrieval
    mock_get_active = AsyncMock(return_value=ticket)

    # Mock add_message_to_ticket to return GRATITUDE
    mock_add_message = AsyncMock(return_value=TicketUpdateResult.GRATITUDE)

    # Mock message object
    message = AsyncMock()
    message.text = "Spasibo"
    message.from_user.id = 123
    message.chat.id = 123
    message.caption = None
    message.photo = None
    message.document = None

    # Explicitly mock message.answer to return a mock object
    message.answer = AsyncMock()

    state = AsyncMock()

    # Apply patches
    with patch('handlers.telegram.get_active_ticket', mock_get_active), \
         patch('handlers.telegram.add_message_to_ticket', mock_add_message), \
         patch('handlers.telegram.FAQService') as mock_faq:

        # Execute handler
        await telegram.handle_message_content(message, state, mock_bot, async_session)

        # Assertions
        mock_get_active.assert_called_once() # Should check ticket
        mock_add_message.assert_called_once() # Should add message

        # KEY ASSERTION: Bot should answer with specific gratitude text
        message.answer.assert_called_with("Рад был помочь! Обращайтесь ещё. 🤝")

        # Should NOT trigger FAQ
        mock_faq.find_match.assert_not_called()

@pytest.mark.asyncio
async def test_reopen_response(async_session, mock_bot):
    """Test that normal text triggers REOPENED result and specific message."""

    user = User(id=1, external_id=123, source=SourceType.TELEGRAM)
    ticket = Ticket(
        id=1, user_id=1, status=TicketStatus.CLOSED, daily_id=1, user=user
    )

    mock_get_active = AsyncMock(return_value=ticket)
    mock_add_message = AsyncMock(return_value=TicketUpdateResult.REOPENED)

    message = AsyncMock()
    message.text = "I have a problem again"
    message.from_user.id = 123
    message.chat.id = 123
    message.caption = None
    message.photo = None
    message.document = None
    message.answer = AsyncMock()

    state = AsyncMock()

    with patch('handlers.telegram.get_active_ticket', mock_get_active), \
         patch('handlers.telegram.add_message_to_ticket', mock_add_message):

        await telegram.handle_message_content(message, state, mock_bot, async_session)

        message.answer.assert_called_with("✅ Сообщение добавлено. Ваш тикет был переоткрыт, оператор скоро ответит.")


@pytest.mark.asyncio
async def test_faq_interruption_prevention(async_session, mock_bot):
    """Test that active ticket prevents FAQ check."""

    user = User(id=1, external_id=123, source=SourceType.TELEGRAM)
    ticket = Ticket(
        id=1, user_id=1, status=TicketStatus.IN_PROGRESS, daily_id=1, user=user
    )

    mock_get_active = AsyncMock(return_value=ticket)
    mock_add_message = AsyncMock(return_value=TicketUpdateResult.ADDED)

    message = AsyncMock()
    message.text = "Where is the dorm?" # This usually triggers FAQ
    message.from_user.id = 123
    message.chat.id = 123
    message.caption = None
    message.photo = None
    message.document = None
    message.answer = AsyncMock()

    state = AsyncMock()

    with patch('handlers.telegram.get_active_ticket', mock_get_active), \
         patch('handlers.telegram.add_message_to_ticket', mock_add_message), \
         patch('handlers.telegram.FAQService') as mock_faq:

        await telegram.handle_message_content(message, state, mock_bot, async_session)

        # Verify order: Ticket checked, Message added.
        mock_get_active.assert_called_once()
        mock_add_message.assert_called_once()

        # FAQ Service should NOT be called even if text matches FAQ keyword
        mock_faq.find_match.assert_not_called()
