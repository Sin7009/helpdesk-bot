import pytest
import html
from unittest.mock import AsyncMock, MagicMock, patch
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

def create_message_mock(message_id: int):
    """Helper to create a mock message object with a valid integer message_id."""
    msg = MagicMock()
    msg.message_id = message_id
    return msg

@pytest.mark.asyncio
async def test_ticket_creation_sanitization(test_session):
    bot = AsyncMock()
    # Configure send_message to return a mock message with an ID
    bot.send_message.return_value = create_message_mock(1001)

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
    # Configure send_message to return a mock message with an ID
    bot.send_message.return_value = create_message_mock(1001)

    # Create a ticket first
    ticket = await create_ticket(
        test_session, user_id=456, source="tg", text="Safe", bot=bot, category_name="General"
    )
    bot.reset_mock()
    # Ensure next calls also return a valid message mock
    bot.send_message.return_value = create_message_mock(1002)

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

@pytest.mark.asyncio
async def test_admin_close_ticket_injection(test_session):
    """
    Simulates an admin clicking 'Close' on a ticket notification where the
    original text contained characters that look like HTML tags (e.g., <script>).
    """
    from handlers import admin
    from aiogram import types
    from database.models import Ticket, TicketStatus, User, SourceType, Category

    # 1. Setup Data
    user = User(external_id=999, source=SourceType.TELEGRAM, full_name="Hacker")
    category = Category(name="Test")
    test_session.add(user)
    test_session.add(category)
    await test_session.commit()

    ticket = Ticket(
        user_id=user.id, daily_id=1, category_id=category.id,
        source=SourceType.TELEGRAM, status=TicketStatus.NEW,
        question_text="<script>alert(1)</script>"
    )
    test_session.add(ticket)
    await test_session.commit()

    # 2. Mock Objects
    bot = AsyncMock()
    # Note: send_message is not called here (edit_text is used), but if it were, we'd need to mock return

    # Callback Object
    callback = AsyncMock(spec=types.CallbackQuery)
    # Fix nested mock attribute
    callback.from_user = MagicMock()
    callback.from_user.id = 777 # Admin ID
    callback.data = f"close_{ticket.id}"

    # The message text as seen by the bot
    callback.message = AsyncMock(spec=types.Message)
    callback.message.text = "Ticket #1\nText: <script>alert(1)</script>"
    callback.message.edit_text = AsyncMock()

    # 3. Patch dependencies
    # Context Manager for new_session
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = test_session
    mock_session_ctx.__aexit__.return_value = None

    with patch("handlers.admin.new_session", return_value=mock_session_ctx), \
         patch("handlers.admin.is_admin_or_mod", return_value=True):

        # 4. Execute Attack
        await admin.close_ticket_btn(callback, bot)

    # 5. Assert Fix (The test passes if the vulnerability is GONE)

    assert callback.message.edit_text.called
    args, kwargs = callback.message.edit_text.call_args

    sent_text = args[0]
    parse_mode = kwargs.get('parse_mode')

    # If FIXED:
    # 1. parse_mode IS "HTML"
    # 2. sent_text contains "&lt;script&gt;" (ESCAPED)
    assert parse_mode == "HTML"
    assert "&lt;script&gt;" in sent_text
    assert "<script>" not in sent_text

@pytest.mark.asyncio
async def test_history_sanitization(test_session):
    """
    Tests that ticket history included in notifications is properly sanitized.
    Vulnerability: The system includes the summary of previous tickets in the admin notification.
    If a previous ticket had malicious HTML, it might be injected into the new notification.
    """
    bot = AsyncMock()
    # Configure send_message to return a mock message with an ID
    bot.send_message.return_value = create_message_mock(1001)

    user_id = 1001

    # 1. Create first ticket with malicious text
    # Short enough to fit in summary without slicing (usually 30 chars)
    malicious_text = "<b>HACK</b>"
    await create_ticket(
        test_session, user_id=user_id, source="tg", text=malicious_text,
        bot=bot, category_name="General", user_full_name="Attacker"
    )

    bot.reset_mock()
    bot.send_message.return_value = create_message_mock(1002)

    # 2. Create second ticket
    # The notification for this ticket will include the history (Ticket 1)
    await create_ticket(
        test_session, user_id=user_id, source="tg", text="Normal text",
        bot=bot, category_name="General", user_full_name="Attacker"
    )

    # 3. Verify notification content
    assert bot.send_message.called
    args, kwargs = bot.send_message.call_args
    sent_text = args[1]

    # Debug print
    print(f"Sent text: {sent_text}")

    # We expect the history section to contain the ESCAPED version of Ticket 1's text
    # Should contain "&lt;b&gt;HACK&lt;/b&gt;"
    # Should NOT contain "<b>HACK</b>"

    assert "&lt;b&gt;HACK&lt;/b&gt;" in sent_text
    assert "<b>HACK</b>" not in sent_text
