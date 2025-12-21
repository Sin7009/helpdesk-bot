"""Test for race condition fix in daily_id generation.

This test ensures that the atomic counter prevents duplicate daily_id values
even when multiple tickets are created concurrently.
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from database.models import Base, Ticket, User, Category, DailyTicketCounter
from services.ticket_service import create_ticket, get_next_daily_id
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
async def test_atomic_daily_id_generation(test_session):
    """Test that daily_id is generated atomically without race conditions."""
    bot = AsyncMock()

    # Create a user
    user = User(external_id=100, source="tg", username="tester", full_name="Tester")
    test_session.add(user)
    await test_session.commit()

    # Create multiple tickets sequentially - should have sequential IDs
    t1 = await create_ticket(test_session, 100, "tg", "First", bot, "Cat1", "Tester")
    assert t1.daily_id == 1

    t2 = await create_ticket(test_session, 100, "tg", "Second", bot, "Cat1", "Tester")
    assert t2.daily_id == 2

    t3 = await create_ticket(test_session, 100, "tg", "Third", bot, "Cat1", "Tester")
    assert t3.daily_id == 3

@pytest.mark.asyncio
async def test_concurrent_ticket_creation(test_engine):
    """Test that concurrent ticket creation doesn't create duplicate daily_ids.
    
    This test simulates multiple tickets being created in quick succession
    to ensure the atomic counter prevents race conditions.
    Note: SQLite serializes writes, so true concurrency isn't possible,
    but this test ensures the counter mechanism works correctly.
    """
    async_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    bot = AsyncMock()

    # Pre-create users and category in separate session
    async with async_session_factory() as setup_session:
        # Create category first
        category = Category(name="General")
        setup_session.add(category)
        
        # Create users
        for i in range(5):
            user = User(external_id=1000 + i, source="tg", username=f"user{i}", full_name=f"User {i}")
            setup_session.add(user)
        await setup_session.commit()

    # Create tickets sequentially (SQLite doesn't support true concurrent writes)
    daily_ids = []
    for i in range(5):
        async with async_session_factory() as session:
            ticket = await create_ticket(
                session, 
                1000 + i, 
                "tg", 
                f"Question from user {1000 + i}", 
                bot, 
                "General", 
                f"User {1000 + i}"
            )
            daily_ids.append(ticket.daily_id)

    # All daily_ids should be unique
    assert len(daily_ids) == len(set(daily_ids)), f"Duplicate daily_ids found: {daily_ids}"
    
    # daily_ids should be sequential from 1 to 5
    assert sorted(daily_ids) == list(range(1, 6)), f"Expected 1-5, got {sorted(daily_ids)}"

@pytest.mark.asyncio
async def test_daily_id_counter_table(test_session):
    """Test that the DailyTicketCounter table works correctly."""
    today = datetime.now().date()
    
    # Get first daily_id
    daily_id_1 = await get_next_daily_id(test_session)
    assert daily_id_1 == 1
    
    # Verify counter row was created
    stmt = select(DailyTicketCounter).where(DailyTicketCounter.date == today)
    result = await test_session.execute(stmt)
    counter = result.scalar_one()
    assert counter.counter == 1
    assert counter.date == today
    
    # Get next daily_id
    daily_id_2 = await get_next_daily_id(test_session)
    assert daily_id_2 == 2
    
    # Verify counter was incremented
    await test_session.refresh(counter)
    assert counter.counter == 2

@pytest.mark.asyncio
async def test_daily_id_resets_each_day(test_session):
    """Test that daily_id resets for each new day."""
    bot = AsyncMock()
    
    # Create user
    user = User(external_id=200, source="tg", username="tester", full_name="Tester")
    test_session.add(user)
    await test_session.commit()
    
    # Simulate yesterday's counter
    yesterday = datetime.now().date() - timedelta(days=1)
    old_counter = DailyTicketCounter(date=yesterday, counter=50)
    test_session.add(old_counter)
    await test_session.commit()
    
    # Create ticket today - should start from 1
    ticket = await create_ticket(test_session, 200, "tg", "Today's ticket", bot, "General", "Tester")
    assert ticket.daily_id == 1
    
    # Verify separate counter exists for today
    today = datetime.now().date()
    stmt = select(DailyTicketCounter).where(DailyTicketCounter.date == today)
    result = await test_session.execute(stmt)
    today_counter = result.scalar_one()
    assert today_counter.counter == 1
    assert today_counter.date == today
