import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ticket_service import add_message_to_ticket
from database.models import Ticket, User, Category, TicketStatus
import datetime

@pytest.mark.asyncio
async def test_notification_truncation_long_message():
    """
    Test that a very long message (exceeding Telegram limit) is truncated properly
    and does not cause an exception during notification.
    """
    # Mock dependencies
    session = AsyncMock()
    session.add = MagicMock()
    bot = AsyncMock()

    # Setup Ticket
    user = User(id=1, external_id=123, full_name="Test User", source="tg")
    category = Category(id=1, name="Test Category")
    ticket = Ticket(
        id=1,
        user_id=1,
        category_id=1,
        daily_id=10,
        created_at=datetime.datetime.now(),
        user=user,
        category=category,
        status=TicketStatus.IN_PROGRESS
    )

    # Generate huge text (e.g. 5000 chars)
    huge_text = "A" * 5000

    # Execute function
    await add_message_to_ticket(session, ticket, huge_text, bot)

    # Verify Admin Notification
    assert bot.send_message.called, "Admin was not notified about new message!"

    # Verify content length
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # Assert length is safe
    assert len(sent_text) <= 4096, f"Message length {len(sent_text)} exceeds 4096 limit!"

    # Assert truncation marker exists
    assert "... (truncated)" in sent_text or "...(limit)" in sent_text
