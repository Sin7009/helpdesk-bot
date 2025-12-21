import pytest
import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, Ticket, TicketStatus, User, SourceType, Category
from services.ticket_service import create_ticket
from unittest.mock import AsyncMock

# --- FIXTURES ---

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    async_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session

@pytest.fixture
def mock_bot():
    return AsyncMock()

# --- TEST ---

@pytest.mark.asyncio
async def test_ticket_id_generation_gap_handling(db_session: AsyncSession, mock_bot):
    """
    Tests that the atomic counter approach prevents ID gaps and race conditions.
    With the new DailyTicketCounter table, IDs are always sequential
    without gaps because they come from an atomic counter.
    """
    # 1. Setup: Create a user and category
    user = User(external_id=12345, source=SourceType.TELEGRAM, username="TestUser")
    db_session.add(user)
    category = Category(name="TestCat")
    db_session.add(category)
    await db_session.flush()

    # 2. Create tickets using the service (which now uses atomic counter)
    # This ensures IDs are always sequential
    ticket1 = await create_ticket(
        db_session, user.external_id, SourceType.TELEGRAM, "First question", mock_bot, "TestCat"
    )
    assert ticket1.daily_id == 1

    ticket2 = await create_ticket(
        db_session, user.external_id, SourceType.TELEGRAM, "Second question", mock_bot, "TestCat"
    )
    assert ticket2.daily_id == 2

    ticket3 = await create_ticket(
        db_session, user.external_id, SourceType.TELEGRAM, "Third question", mock_bot, "TestCat"
    )
    assert ticket3.daily_id == 3

    # 3. Even if we manually update a ticket's daily_id (creating a "gap"),
    # the counter continues from where it left off because it's stored separately
    ticket2.daily_id = 99  # Manual modification (should never happen in production)
    await db_session.commit()

    # 4. New tickets still get sequential IDs from the counter
    ticket4 = await create_ticket(
        db_session, user.external_id, SourceType.TELEGRAM, "Fourth question", mock_bot, "TestCat"
    )
    # Counter doesn't care about gaps in actual ticket daily_ids
    # It just increments its own value
    assert ticket4.daily_id == 4, f"Expected daily_id 4 (counter continues), but got {ticket4.daily_id}"

