"""Tests for scheduler service."""
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, Ticket, Category, User, TicketStatus, SourceType
from services.scheduler import send_daily_statistics

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
async def test_send_daily_statistics_empty_db():
    """Test sending statistics when database is empty."""
    bot = AsyncMock()
    
    # Mock new_session context manager
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result
    
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = AsyncMock()
    
    with patch('services.scheduler.new_session', return_value=mock_session_ctx):
        await send_daily_statistics(bot)
    
    # Verify bot.send_message was called
    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    message_text = args[1]
    
    # Check that the message contains statistics
    assert "Статистика за" in message_text
    assert "Всего запросов: 0" in message_text
    assert "Закрыто: 0" in message_text
    assert "Нет данных" in message_text or "Топ тем:" in message_text
    assert kwargs['parse_mode'] == "HTML"


@pytest.mark.asyncio
async def test_send_daily_statistics_with_data(test_session):
    """Test sending statistics with actual data."""
    # Create test data
    user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
    test_session.add(user)
    await test_session.commit()
    
    category1 = Category(name="IT")
    category2 = Category(name="Общежитие")
    test_session.add_all([category1, category2])
    await test_session.commit()
    
    # Create tickets for today
    today = datetime.datetime.now()
    ticket1 = Ticket(
        user_id=user.id,
        category_id=category1.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=1,
        question_text="Test question 1",
        created_at=today
    )
    ticket2 = Ticket(
        user_id=user.id,
        category_id=category1.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.CLOSED,
        daily_id=2,
        question_text="Test question 2",
        created_at=today,
        closed_at=today
    )
    ticket3 = Ticket(
        user_id=user.id,
        category_id=category2.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=3,
        question_text="Test question 3",
        created_at=today
    )
    test_session.add_all([ticket1, ticket2, ticket3])
    await test_session.commit()
    
    bot = AsyncMock()
    
    # Mock new_session to return our test_session
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = test_session
    mock_session_ctx.__aexit__.return_value = AsyncMock()
    
    with patch('services.scheduler.new_session', return_value=mock_session_ctx):
        await send_daily_statistics(bot)
    
    # Verify bot.send_message was called
    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    message_text = args[1]
    
    # Check that the message contains correct statistics
    assert "Статистика за" in message_text
    assert "Всего запросов: 3" in message_text
    assert "Закрыто: 1" in message_text
    assert "Топ тем:" in message_text
    # Should show IT first (2 tickets) then Общежитие (1 ticket)
    assert "IT: 2" in message_text
    assert "Общежитие: 1" in message_text


@pytest.mark.asyncio
async def test_send_daily_statistics_handles_error():
    """Test that statistics sending handles errors gracefully."""
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Network error")
    
    # Mock new_session context manager
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result
    
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = AsyncMock()
    
    with patch('services.scheduler.new_session', return_value=mock_session_ctx):
        # Should not raise exception
        await send_daily_statistics(bot)
    
    # Verify bot.send_message was called despite error
    assert bot.send_message.called


@pytest.mark.asyncio
async def test_send_daily_statistics_excludes_old_tickets(test_session):
    """Test that statistics only counts today's tickets."""
    # Create test data
    user = User(external_id=456, source=SourceType.TELEGRAM, full_name="Test User")
    test_session.add(user)
    await test_session.commit()
    
    category = Category(name="Test")
    test_session.add(category)
    await test_session.commit()
    
    # Create ticket from yesterday
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    old_ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.CLOSED,
        daily_id=1,
        question_text="Old question",
        created_at=yesterday,
        closed_at=yesterday
    )
    
    # Create ticket from today
    today = datetime.datetime.now()
    new_ticket = Ticket(
        user_id=user.id,
        category_id=category.id,
        source=SourceType.TELEGRAM,
        status=TicketStatus.NEW,
        daily_id=2,
        question_text="New question",
        created_at=today
    )
    
    test_session.add_all([old_ticket, new_ticket])
    await test_session.commit()
    
    bot = AsyncMock()
    
    # Mock new_session to return our test_session
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = test_session
    mock_session_ctx.__aexit__.return_value = AsyncMock()
    
    with patch('services.scheduler.new_session', return_value=mock_session_ctx):
        await send_daily_statistics(bot)
    
    # Verify statistics only count today's ticket
    args, kwargs = bot.send_message.call_args
    message_text = args[1]
    
    # Should only count 1 ticket created today, 0 closed today
    assert "Всего запросов: 1" in message_text
    assert "Закрыто: 0" in message_text
