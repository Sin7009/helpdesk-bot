import pytest
import html
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from services.ticket_service import create_ticket, add_message_to_ticket
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
async def test_create_ticket_html_injection(test_session):
    # Mock Bot
    bot = AsyncMock()

    # Input with HTML
    malicious_text = "<b>Bold</b> & <script>alert(1)</script>"

    # Create ticket
    await create_ticket(
        test_session,
        user_id=12345,
        source="tg",
        text=malicious_text,
        bot=bot,
        category_name="General",
        user_full_name="Test User"
    )

    # Verify send_message called
    assert bot.send_message.called

    # Get args
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # Verify it IS escaped
    escaped_text = html.escape(malicious_text)
    assert f"Текст: {escaped_text}" in sent_text

    # Ensure raw tags are NOT present
    assert "<b>Bold</b>" not in sent_text
    assert "<script>" not in sent_text

@pytest.mark.asyncio
async def test_add_message_html_injection(test_session):
    # Mock Bot
    bot = AsyncMock()
    malicious_text = "<i>Italic</i>"

    # Create ticket first
    ticket = await create_ticket(
        test_session,
        user_id=12345,
        source="tg",
        text="Initial",
        bot=bot,
        category_name="General",
        user_full_name="Test User"
    )

    # Reset mock to clear previous calls
    bot.send_message.reset_mock()

    # Add message with HTML
    await add_message_to_ticket(test_session, ticket, malicious_text, bot)

    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # Verify it IS escaped
    escaped_text = html.escape(malicious_text)
    assert f"Текст: {escaped_text}" in sent_text
    assert "<i>Italic</i>" not in sent_text
