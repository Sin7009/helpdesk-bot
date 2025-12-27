import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.ticket_service import TicketUpdateResult, add_message_to_ticket
from database.models import Ticket, TicketStatus, User, Message
from handlers.telegram import handle_message_content

@pytest.mark.asyncio
async def test_add_message_to_ticket_returns_enum(async_session):
    """Test that add_message_to_ticket returns correct Enum values."""
    # Use async_session fixture instead of test_session
    session = async_session

    # Mock bot
    bot = MagicMock()
    bot.send_message = AsyncMock()

    # Create dummy ticket
    ticket = Ticket(
        id=1, daily_id=1, user_id=1, status=TicketStatus.IN_PROGRESS,
        question_text="Q", priority="normal"
    )
    # Mock relations (since we are not using real DB objects with lazy loading here)
    ticket.user = User(id=1, external_id=123, full_name="Test")
    ticket.category = MagicMock()
    ticket.category.name = "Test"

    # Test ADDED
    result = await add_message_to_ticket(session, ticket, "New msg", bot)
    assert result == TicketUpdateResult.ADDED
    assert ticket.status == TicketStatus.IN_PROGRESS

    # Test REOPENED
    ticket.status = TicketStatus.CLOSED
    result = await add_message_to_ticket(session, ticket, "Help me", bot)
    assert result == TicketUpdateResult.REOPENED
    assert ticket.status == TicketStatus.IN_PROGRESS

    # Test GRATITUDE
    ticket.status = TicketStatus.CLOSED
    result = await add_message_to_ticket(session, ticket, "Thanks!", bot)
    assert result == TicketUpdateResult.GRATITUDE
    assert ticket.status == TicketStatus.CLOSED

@pytest.mark.asyncio
async def test_handler_smart_gratitude_flow():
    """Test the smart gratitude flow in handle_message_content."""

    # Mock dependencies
    message = AsyncMock()
    message.text = "Thanks!"
    message.from_user.id = 123
    message.chat.id = 12345
    message.photo = None
    message.document = None

    state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)

    bot = AsyncMock()
    session = AsyncMock()

    # Mock get_active_ticket -> None (User has no active ticket)
    # Mock get_latest_ticket -> CLOSED ticket
    mock_ticket = MagicMock()
    mock_ticket.status = TicketStatus.CLOSED
    mock_ticket.id = 1

    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active, \
         patch("handlers.telegram.get_latest_ticket", new_callable=AsyncMock) as mock_get_latest, \
         patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg, \
         patch("handlers.telegram.is_within_working_hours", return_value=True):

        mock_get_active.return_value = None
        mock_get_latest.return_value = mock_ticket

        # Scenario 1: Gratitude
        mock_add_msg.return_value = TicketUpdateResult.GRATITUDE

        await handle_message_content(message, state, bot, session)

        # Verify it tried to add message to the closed ticket
        mock_add_msg.assert_called_once()
        # Verify it sent the "You're welcome" message
        message.answer.assert_called_with("Рады помочь! Обращайтесь ещё. 👋")
        state.clear.assert_called()

@pytest.mark.asyncio
async def test_handler_smart_reopen_flow():
    """Test the smart reopen flow in handle_message_content."""

    # Mock dependencies
    message = AsyncMock()
    message.text = "My issue is back"
    message.from_user.id = 123
    message.chat.id = 12345
    message.photo = None
    message.document = None

    state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)

    bot = AsyncMock()
    session = AsyncMock()

    # Mock get_active_ticket -> None
    # Mock get_latest_ticket -> CLOSED ticket
    mock_ticket = MagicMock()
    mock_ticket.status = TicketStatus.CLOSED

    with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active, \
         patch("handlers.telegram.get_latest_ticket", new_callable=AsyncMock) as mock_get_latest, \
         patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg:

        mock_get_active.return_value = None
        mock_get_latest.return_value = mock_ticket

        # Scenario 2: Reopen
        mock_add_msg.return_value = TicketUpdateResult.REOPENED

        await handle_message_content(message, state, bot, session)

        # Verify it sent the "Reopened" message
        message.answer.assert_called_with("🔄 Мы переоткрыли вашу последнюю заявку. Оператор увидит сообщение.")
        state.clear.assert_called()
