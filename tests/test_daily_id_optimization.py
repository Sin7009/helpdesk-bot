import asyncio
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func, desc
from database.models import Base, Ticket, TicketStatus, SourceType, User, Category
from services.ticket_service import create_ticket
from unittest.mock import AsyncMock

# Use in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine):
    async_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session

@pytest.mark.asyncio
async def test_daily_id_generation(test_session):
    from unittest.mock import MagicMock
    bot = AsyncMock()
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message

    # Create a user to avoid issues
    user = User(external_id=100, source="tg", username="tester", full_name="Tester")
    test_session.add(user)
    await test_session.commit()

    # Create tickets
    # 1st ticket
    t1 = await create_ticket(test_session, 100, "tg", "First", bot, "Cat1", "Tester")
    assert t1.daily_id == 1

    # 2nd ticket
    # Wait a tiny bit or force created_at if possible, but created_at is server_default.
    # We rely on execution order which usually results in slightly different times or at least correct order.
    # In SQLite, time resolution might be limited, but let's see.
    t2 = await create_ticket(test_session, 100, "tg", "Second", bot, "Cat1", "Tester")
    assert t2.daily_id == 2

    # 3rd ticket
    t3 = await create_ticket(test_session, 100, "tg", "Third", bot, "Cat1", "Tester")
    assert t3.daily_id == 3

    # Now simulate a gap if we can delete, but create_ticket doesn't support deleting.
    # But we can verify that the IDs are sequential.

@pytest.mark.asyncio
async def test_daily_id_reset(test_session):
    # This is hard to test without mocking datetime.datetime.now() inside the service
    # or manually inserting tickets with past dates.
    # Let's try inserting a ticket from yesterday manually.

    yesterday = datetime.now() - timedelta(days=1)

    user = User(external_id=101, source="tg", username="tester2", full_name="Tester2")
    test_session.add(user)

    # Insert old ticket
    old_ticket = Ticket(
        user_id=1, # assuming user id 1
        daily_id=999,
        source="tg",
        question_text="Old",
        status=TicketStatus.CLOSED,
        created_at=yesterday
    )
    test_session.add(old_ticket)
    await test_session.commit()

    from unittest.mock import MagicMock
    bot = AsyncMock()
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message
    # Now create a new ticket today
    t_new = await create_ticket(test_session, 101, "tg", "New Day", bot, "Cat1", "Tester2")

    # Should start from 1
    assert t_new.daily_id == 1
