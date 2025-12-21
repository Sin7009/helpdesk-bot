import pytest
import html
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
async def test_create_ticket_handles_large_payload_safely(test_session):
    """
    Verified Fix: Ensures that excessively long messages are TRUNCATED
    before sending to admin, preventing silent failures.

    Previously: Messages > 4096 chars caused exceptions which were swallowed.
    Now: Messages are truncated to be safe.
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

    # 2. The admin notification SUCCEEDED (Mock side effect NOT triggered)
    # We verify bot.send_message was called with a SAFE text length
    assert bot.send_message.called
    call_args = bot.send_message.call_args
    sent_text = call_args.args[1]

    # Assert length is safe
    assert len(sent_text) <= 4096

    # Assert truncation happened
    assert "... (truncated)" in sent_text or "...(limit)" in sent_text

@pytest.mark.asyncio
async def test_create_ticket_handles_unescaped_html_input(test_session):
    """
    Verified Fix: Ensures that unescaped HTML characters in user input
    are SANITIZED and do NOT cause admin notifications to fail.

    Previously: Input like "<3" caused HTML parsing errors.
    Now: "<3" becomes "&lt;3" and is safe.
    """

    # Mock Bot
    bot = AsyncMock()

    # Simulate Telegram API error on invalid HTML
    async def side_effect(*args, **kwargs):
        text = args[1]
        parse_mode = kwargs.get('parse_mode')

        # If we are in HTML mode and find unescaped tag-like chars
        if parse_mode == "HTML":
            # Check for the specific problematic input we are testing
            # If sanitization works, "<3" should NOT be present (it should be &lt;3)
            if "<3" in text:
                raise Exception("Bad Request: Can't parse entities: ...")

        return MagicMock()

    bot.send_message.side_effect = side_effect

    # Input that mimics a common user typo or usage (e.g. heart emoji text)
    bad_input = "Hello admin! I love this bot <3 please help me."

    # Execute
    ticket = await create_ticket(
        test_session,
        user_id=88888,
        source="tg",
        text=bad_input,
        bot=bot,
        category_name="Bug",
        user_full_name="InnocentUser"
    )

    # ASSERTIONS

    # 1. Ticket created in DB
    assert ticket is not None
    assert ticket.id is not None

    # 2. Notification logic executed successfully (No Exception raised by side_effect)
    assert bot.send_message.called

    # Verify the text passed to the bot IS SANITIZED
    call_args = bot.send_message.call_args
    sent_text = call_args.args[1]

    # Original bad input should NOT be in the sent text literally
    assert bad_input not in sent_text

    # Escaped version SHOULD be in the sent text
    expected_safe_text = html.escape(bad_input)
    assert expected_safe_text in sent_text
