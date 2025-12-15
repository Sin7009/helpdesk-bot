import pytest
import html
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from services.ticket_service import create_ticket, add_message_to_ticket

# Setup in-memory DB
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_session():
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
async def test_ticket_creation_sanitization(test_session):
    bot = AsyncMock()
    malicious_text = "Hello <b>bold</b> <a href='http://evil.com'>click me</a>"

    await create_ticket(
        test_session,
        user_id=123,
        source="tg",
        text=malicious_text,
        bot=bot,
        category_name="General",
        user_full_name="Attacker"
    )

    # Check what was sent to bot
    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # Verify that the malicious text is escaped in the output
    escaped_text = html.escape(malicious_text)
    assert escaped_text in sent_text

    # Verify that raw tags are NOT in the output
    # This checks that we don't see unescaped tags like <b> or <a href
    assert "<b>bold</b>" not in sent_text
    assert "<a href='http://evil.com'>" not in sent_text

@pytest.mark.asyncio
async def test_add_message_sanitization(test_session):
    bot = AsyncMock()
    # Create a ticket first
    ticket = await create_ticket(
        test_session, user_id=456, source="tg", text="Safe", bot=bot, category_name="General"
    )
    bot.reset_mock()

    # Refresh ticket to load relationships (simulating real app behavior)
    # This prevents MissingGreenlet error when accessing ticket.user/ticket.category
    await test_session.refresh(ticket, ["user", "category"])

    malicious_text = "Broken <tag"

    await add_message_to_ticket(test_session, ticket, malicious_text, bot)

    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # "Broken <tag" should become "Broken &lt;tag"
    assert "Broken &lt;tag" in sent_text
    assert "Broken <tag" not in sent_text
