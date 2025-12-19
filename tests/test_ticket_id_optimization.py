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
    Demonstrates that count(*) strategy fails when there are gaps in IDs,
    and validates that finding the max ID is safer.
    """
    # 1. Setup: Create a user and category
    user = User(external_id=12345, source=SourceType.TELEGRAM, username="TestUser")
    db_session.add(user)
    category = Category(name="TestCat")
    db_session.add(category)
    await db_session.flush()

    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 2. Create 2 tickets with daily_id 1 and 2
    t1 = Ticket(
        user_id=user.id, daily_id=1, category_id=category.id,
        source=SourceType.TELEGRAM, status=TicketStatus.NEW,
        created_at=today_start + datetime.timedelta(hours=1)
    )
    t2 = Ticket(
        user_id=user.id, daily_id=2, category_id=category.id,
        source=SourceType.TELEGRAM, status=TicketStatus.NEW,
        created_at=today_start + datetime.timedelta(hours=2)
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.commit()

    # 3. Simulate a manual gap: Update t2 to have daily_id = 5
    # This simulates a situation where tickets 3 and 4 were deleted,
    # or IDs were skipped for some reason.
    t2.daily_id = 5
    await db_session.commit()

    # 4. Verify current state
    # Count of tickets today = 2.
    # Existing IDs: 1, 5.

    # Run the query used in CURRENT implementation (count)
    stmt_count = select(func.count(Ticket.id)).where(Ticket.created_at >= today_start)
    count_result = await db_session.execute(stmt_count)
    today_count = count_result.scalar() or 0
    next_id_by_count = today_count + 1

    # Let's verify the NEW logic behavior (max + 1)
    stmt_last = select(Ticket.daily_id).where(Ticket.created_at >= today_start).order_by(desc(Ticket.created_at)).limit(1)
    result_last = await db_session.execute(stmt_last)
    last_daily_id = result_last.scalar() or 0
    next_id_by_max = last_daily_id + 1

    # Assertions
    # In this scenario (1, 5), count gives 3. Max gives 6.

    assert today_count == 2
    assert next_id_by_count == 3

    assert last_daily_id == 5
    assert next_id_by_max == 6

    # 5. Now try to actually create a ticket using the service
    # (which currently uses count logic, until we fix it)

    new_ticket = await create_ticket(
        db_session, user.external_id, SourceType.TELEGRAM, "New question", mock_bot, "TestCat"
    )

    # Once we fix the code, this should be 6.
    # For now, it will be 3 (count + 1).
    # Since we want to pass this test *after* the fix, we check if logic is updated?
    # Or we can assert the *current* buggy behavior to prove it, then change assertions?

    # I will assert the NEW desired behavior, so the test will FAIL initially (demonstrating the issue/need for fix)
    # But for "Verify" step later, I want it to pass.
    # Wait, the prompt says "Verify the optimization works as expected".

    # Assert that the new ticket ID follows the MAX logic (safe for gaps)
    # The gaps scenario (IDs 1, 5) means the next ID should be 6.
    # The unsafe COUNT logic would have produced 3.
    assert new_ticket.daily_id == 6, f"Expected daily_id 6 (Max+1), but got {new_ticket.daily_id}"
