import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, User, Ticket, Message, SourceType, SenderRole, TicketStatus, Category
# from services.user_service import get_or_create_user # Seems like this service might not exist or wasn't provided in the file list
from services.ticket_service import create_ticket, get_active_ticket, add_message_to_ticket
from unittest.mock import AsyncMock

# Use an in-memory SQLite database for testing
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
async def test_ticket_flow(test_session):
    # Mock Bot
    from unittest.mock import MagicMock
    bot = AsyncMock()
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message

    # 1. Test create ticket
    # This automatically handles user creation if needed in updated logic
    ticket = await create_ticket(
        test_session,
        user_id=12345,
        source="tg",
        text="Help me",
        bot=bot,
        category_name="General",
        user_full_name="Test User"
    )

    assert ticket is not None
    assert ticket.status == TicketStatus.NEW
    assert ticket.daily_id == 1

    # Verify User was created
    from sqlalchemy import select
    stmt = select(User).where(User.external_id == 12345)
    user = (await test_session.execute(stmt)).scalar_one()
    assert user.full_name == "Test User"

    # Verify Category was created
    stmt = select(Category).where(Category.name == "General")
    category = (await test_session.execute(stmt)).scalar_one()
    assert category.id == ticket.category_id

    # 2. Test get active ticket
    active_ticket = await get_active_ticket(test_session, 12345, "tg")
    assert active_ticket is not None
    assert active_ticket.id == ticket.id

    # 3. Add message
    await add_message_to_ticket(test_session, ticket, "More info", bot)

    # Verify messages
    stmt = select(Message).where(Message.ticket_id == ticket.id)
    messages = (await test_session.execute(stmt)).scalars().all()
    assert len(messages) == 2 # Initial + added
    assert messages[0].text == "Help me"
    assert messages[1].text == "More info"

    # 4. Close ticket (Manual status update as in handler)
    ticket.status = TicketStatus.CLOSED
    await test_session.commit()

    # Verify no active ticket
    active_ticket = await get_active_ticket(test_session, 12345, "tg")
    assert active_ticket is None
