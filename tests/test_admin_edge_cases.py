"""Additional tests for admin handler edge cases."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from handlers.admin import process_reply
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, Ticket, User, Category, TicketStatus, SourceType

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_session():
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_process_reply_empty_text(test_session):
    """Test that process_reply handles empty text gracefully."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create test ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    # Try to reply with empty text
    await process_reply(bot, test_session, ticket.id, "", message, close=False)
    
    # Should show error message
    message.answer.assert_called_once()
    assert "не может быть пустым" in message.answer.call_args[0][0]
    # Should not send to user
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_reply_whitespace_only(test_session):
    """Test that process_reply handles whitespace-only text."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create test ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    # Try to reply with whitespace
    await process_reply(bot, test_session, ticket.id, "   \n\t  ", message, close=False)
    
    # Should show error message
    message.answer.assert_called_once()
    assert "не может быть пустым" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_reply_nonexistent_ticket(test_session):
    """Test that process_reply handles nonexistent ticket ID."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    
    # Try to reply to non-existent ticket
    await process_reply(bot, test_session, 99999, "Test reply", message, close=False)
    
    # Should show error message
    message.answer.assert_called_once()
    assert "не найден" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_reply_already_closed_ticket(test_session):
    """Test that process_reply handles already closed tickets."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    
    # Create closed ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.CLOSED,  # Already closed
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    # Try to reply to closed ticket
    await process_reply(bot, test_session, ticket.id, "Test reply", message, close=False)
    
    # Should show warning message
    message.answer.assert_called_once()
    assert "уже закрыт" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_reply_bot_send_failure(test_session):
    """Test that process_reply handles bot.send_message failure gracefully."""
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Network error")
    
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create test ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    # Try to reply
    await process_reply(bot, test_session, ticket.id, "Test reply", message, close=False)
    
    # Should show error message to admin
    message.answer.assert_called_once()
    assert "Ошибка отправки" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_reply_strips_text(test_session):
    """Test that process_reply strips whitespace from reply text."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create test ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    # Reply with whitespace around text
    await process_reply(bot, test_session, ticket.id, "  Test reply  \n", message, close=False)
    
    # Check that sent message contains stripped text
    bot.send_message.assert_called_once()
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]
    
    # The reply should be included in the message (stripped)
    assert "Test reply" in sent_text
    # Should not have leading/trailing whitespace in the actual reply text
    assert "  Test reply  " not in sent_text


@pytest.mark.asyncio
async def test_process_reply_changes_status_to_in_progress(test_session):
    """Test that process_reply changes NEW ticket status to IN_PROGRESS."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create NEW ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    ticket_id = ticket.id
    
    # Reply without closing
    await process_reply(bot, test_session, ticket_id, "Test reply", message, close=False)
    
    # Refresh ticket to get updated status
    await test_session.refresh(ticket)
    
    # Status should be IN_PROGRESS
    assert ticket.status == TicketStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_process_reply_closes_ticket_when_requested(test_session):
    """Test that process_reply closes ticket when close=True."""
    bot = AsyncMock()
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.react = AsyncMock()
    
    # Create NEW ticket
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    category = Category(name="Test")
    test_session.add_all([user, category])
    await test_session.commit()
    
    ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question"
    )
    test_session.add(ticket)
    await test_session.commit()
    
    ticket_id = ticket.id
    
    # Reply with closing
    await process_reply(bot, test_session, ticket_id, "Test reply", message, close=True)
    
    # Refresh ticket to get updated status
    await test_session.refresh(ticket)
    
    # Status should be CLOSED
    assert ticket.status == TicketStatus.CLOSED
    assert ticket.closed_at is not None
