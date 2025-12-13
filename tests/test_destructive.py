import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from services.ticket_service import create_ticket
from unittest.mock import AsyncMock, MagicMock
from core.config import settings

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
async def test_create_ticket_silent_notification_failure_on_large_payload(test_session):
    """
    Destructive Test: Verifies that 'create_ticket' silently swallows exceptions
    during admin notification (e.g., when message text is too long for Telegram API).

    Vulnerability: The user is told the ticket is created, but the admin never receives it.
    """

    # Mock Bot
    bot = AsyncMock()

    # Simulate Telegram API error when message is too long (4096+ chars)
    # The actual API raises generic Exceptions or TelegramAPIError.
    # The service code catches 'Exception'.
    async def side_effect(*args, **kwargs):
        text = args[1] # args[0] is chat_id, args[1] is text
        if len(text) > 4096:
            raise Exception("Bad Request: message is too long")
        return MagicMock()

    bot.send_message.side_effect = side_effect

    # Create a massive payload > 4096 chars
    long_text = "A" * 5000

    # Execute the function
    ticket = await create_ticket(
        test_session,
        user_id=99999,
        source="tg",
        text=long_text,
        bot=bot,
        category_name="StressTest",
        user_full_name="Attacker"
    )

    # ASSERTIONS

    # 1. The ticket WAS created in the database (Database Integrity preserved)
    assert ticket is not None
    assert ticket.id is not None

    # 2. The admin notification FAILED (Mock side effect triggered)
    # We verify bot.send_message was called with the large text
    assert bot.send_message.called
    call_args = bot.send_message.call_args
    # The first argument is chat_id, second is text.
    # Depending on how it's called (args vs kwargs).
    # In code: await bot.send_message(settings.TG_ADMIN_ID, admin_text, ...)
    assert len(call_args.args[1]) > 4096

    # 3. The logic SWALLOWED the exception (Function did not crash)
    # This confirms the "silent failure" vulnerability.
    # Admin is unaware of this new ticket.
