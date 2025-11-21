import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, User, Ticket, Message, SourceType, SenderRole, TicketStatus
from services.user_service import get_or_create_user
from services.ticket_service import create_ticket, get_open_ticket, add_message_to_ticket, close_ticket

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
async def test_user_creation(test_session):
    user = await get_or_create_user(test_session, 12345, SourceType.TELEGRAM, "testuser", "Test User")
    assert user.id is not None
    assert user.external_id == 12345
    assert user.source == SourceType.TELEGRAM

    # Test getting existing user
    user2 = await get_or_create_user(test_session, 12345, SourceType.TELEGRAM)
    assert user.id == user2.id

@pytest.mark.asyncio
async def test_ticket_flow(test_session):
    # Create user
    user = await get_or_create_user(test_session, 999, SourceType.VK, "vkuser", "VK User")

    # Verify no open ticket initially
    ticket = await get_open_ticket(test_session, user.id)
    assert ticket is None

    # Create ticket
    new_ticket = await create_ticket(test_session, user.id, SourceType.VK, "Help me!")
    assert new_ticket.status == TicketStatus.NEW
    assert new_ticket.question_text == "Help me!"

    # Verify open ticket exists
    ticket = await get_open_ticket(test_session, user.id)
    assert ticket is not None
    assert ticket.id == new_ticket.id

    # Check messages
    # Note: create_ticket adds the first message
    # We need to refresh to see relations if not eager loaded,
    # but ticket object might not have messages loaded.
    # Let's query messages manually to verify.
    from sqlalchemy import select
    stmt = select(Message).where(Message.ticket_id == ticket.id)
    result = await test_session.execute(stmt)
    messages = result.scalars().all()
    assert len(messages) == 1
    assert messages[0].text == "Help me!"
    assert messages[0].sender_role == SenderRole.USER

    # Add another message
    await add_message_to_ticket(test_session, ticket.id, "More info", SenderRole.USER)

    result = await test_session.execute(stmt)
    messages = result.scalars().all()
    assert len(messages) == 2

    # Close ticket
    await close_ticket(test_session, ticket.id)

    # Verify no open ticket
    ticket = await get_open_ticket(test_session, user.id)
    assert ticket is None
