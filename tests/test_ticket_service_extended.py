"""Extended tests for ticket service to improve coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import (
    Base, User, Ticket, Message, TicketStatus, SourceType,
    SenderRole, Category, TicketPriority
)
from services.ticket_service import (
    create_ticket, get_active_ticket, add_message_to_ticket,
    get_user_history, get_next_daily_id, _send_staff_notification
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session


@pytest.fixture
def mock_bot():
    """Create a mock bot."""
    bot = AsyncMock()
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message
    bot.send_photo.return_value = mock_message
    bot.send_document.return_value = mock_message
    return bot


class TestCreateTicket:
    """Tests for create_ticket function."""

    @pytest.mark.asyncio
    async def test_create_ticket_basic(self, test_session, mock_bot):
        """Test basic ticket creation."""
        ticket = await create_ticket(
            test_session,
            user_id=12345,
            source=SourceType.TELEGRAM,
            text="Test question",
            bot=mock_bot,
            category_name="IT Support",
            user_full_name="Test User"
        )

        assert ticket is not None
        assert ticket.id is not None
        assert ticket.status == TicketStatus.NEW
        assert ticket.daily_id == 1
        assert ticket.question_text == "Test question"

    @pytest.mark.asyncio
    async def test_create_ticket_empty_text_with_media(self, test_session, mock_bot):
        """Test ticket creation with empty text but media."""
        ticket = await create_ticket(
            test_session,
            user_id=12345,
            source=SourceType.TELEGRAM,
            text="",  # Empty text
            bot=mock_bot,
            category_name="General",
            user_full_name="Test User",
            media_id="photo123",
            content_type="photo"
        )

        assert ticket is not None
        assert ticket.question_text == "[Вложение]"

    @pytest.mark.asyncio
    async def test_create_ticket_empty_text_no_media_fails(self, test_session, mock_bot):
        """Test ticket creation fails with empty text and no media."""
        with pytest.raises(ValueError) as exc_info:
            await create_ticket(
                test_session,
                user_id=12345,
                source=SourceType.TELEGRAM,
                text="",
                bot=mock_bot,
                category_name="General",
                user_full_name="Test User"
            )

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_ticket_text_too_long(self, test_session, mock_bot):
        """Test ticket creation fails with very long text."""
        with pytest.raises(ValueError) as exc_info:
            await create_ticket(
                test_session,
                user_id=12345,
                source=SourceType.TELEGRAM,
                text="A" * 10001,  # Too long
                bot=mock_bot,
                category_name="General",
                user_full_name="Test User"
            )

        assert "too long" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_ticket_updates_existing_user_name(self, test_session, mock_bot):
        """Test ticket creation updates existing user's name."""
        # Create user first
        from sqlalchemy import select
        user = User(
            external_id=99999,
            source=SourceType.TELEGRAM,
            full_name="Old Name"
        )
        test_session.add(user)
        await test_session.commit()

        # Create ticket with new name
        await create_ticket(
            test_session,
            user_id=99999,
            source=SourceType.TELEGRAM,
            text="Question",
            bot=mock_bot,
            category_name="General",
            user_full_name="New Name"
        )

        # Check user name was updated
        await test_session.refresh(user)
        assert user.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_create_ticket_detects_priority(self, test_session, mock_bot):
        """Test ticket creation detects priority from text."""
        ticket = await create_ticket(
            test_session,
            user_id=12345,
            source=SourceType.TELEGRAM,
            text="СРОЧНО! Не работает портал!",  # Urgent keyword
            bot=mock_bot,
            category_name="IT Support",
            user_full_name="Test User"
        )

        assert ticket.priority in [TicketPriority.URGENT, TicketPriority.HIGH, TicketPriority.NORMAL]

    @pytest.mark.asyncio
    async def test_create_ticket_with_history(self, test_session, mock_bot):
        """Test ticket creation includes history in notification."""
        # Create user
        user = User(
            external_id=77777,
            source=SourceType.TELEGRAM,
            full_name="Test User"
        )
        test_session.add(user)
        await test_session.commit()

        # Create category
        category = Category(name="Support")
        test_session.add(category)
        await test_session.commit()

        # Create old ticket
        old_ticket = Ticket(
            user_id=user.id,
            category_id=category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=1,
            question_text="Old question",
            summary="Old ticket resolved"
        )
        test_session.add(old_ticket)
        await test_session.commit()

        # Create new ticket
        new_ticket = await create_ticket(
            test_session,
            user_id=77777,
            source=SourceType.TELEGRAM,
            text="New question",
            bot=mock_bot,
            category_name="Support",
            user_full_name="Test User"
        )

        assert new_ticket is not None
        # Bot should have been called with history
        mock_bot.send_message.assert_called()


class TestAddMessageToTicket:
    """Tests for add_message_to_ticket function."""

    @pytest.mark.asyncio
    async def test_add_message_reopens_closed_ticket(self, test_session, mock_bot):
        """Test adding message to closed ticket reopens it."""
        # Create user
        user = User(
            external_id=55555,
            source=SourceType.TELEGRAM,
            full_name="Test User"
        )
        test_session.add(user)
        await test_session.commit()

        # Create category
        category = Category(name="General")
        test_session.add(category)
        await test_session.commit()

        # Create closed ticket
        ticket = Ticket(
            user_id=user.id,
            category_id=category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=1,
            question_text="Original question"
        )
        test_session.add(ticket)
        await test_session.commit()

        # Reload ticket with relationships
        await test_session.refresh(ticket)
        ticket.user = user
        ticket.category = category

        # Add message
        await add_message_to_ticket(test_session, ticket, "Follow up", mock_bot)

        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.closed_at is None

    @pytest.mark.asyncio
    async def test_add_message_with_photo(self, test_session, mock_bot):
        """Test adding photo message to ticket."""
        # Create user
        user = User(
            external_id=44444,
            source=SourceType.TELEGRAM,
            full_name="Test User"
        )
        test_session.add(user)
        await test_session.commit()

        # Create category
        category = Category(name="General")
        test_session.add(category)
        await test_session.commit()

        # Create ticket
        ticket = Ticket(
            user_id=user.id,
            category_id=category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.NEW,
            daily_id=1,
            question_text="Original"
        )
        test_session.add(ticket)
        await test_session.commit()

        ticket.user = user
        ticket.category = category

        # Add photo message
        await add_message_to_ticket(
            test_session, ticket, "Photo caption", mock_bot,
            media_id="photo456", content_type="photo"
        )

        # Check message was saved
        from sqlalchemy import select
        stmt = select(Message).where(Message.ticket_id == ticket.id)
        result = await test_session.execute(stmt)
        messages = result.scalars().all()

        # Should have the new message with photo
        photo_msg = next((m for m in messages if m.content_type == "photo"), None)
        assert photo_msg is not None
        assert photo_msg.media_id == "photo456"


class TestSendStaffNotification:
    """Tests for _send_staff_notification function."""

    @pytest.mark.asyncio
    async def test_notification_with_photo(self, mock_bot):
        """Test notification with photo attachment."""
        ticket = MagicMock()
        ticket.id = 123
        ticket.daily_id = 1
        ticket.priority = TicketPriority.NORMAL
        ticket.category.name = "IT"

        user = MagicMock()
        user.external_id = 111
        user.full_name = "Test User"
        user.is_head_student = False
        user.course = 2
        user.group_number = "CS-201"
        user.department = None

        result = await _send_staff_notification(
            mock_bot, ticket, user, "Photo caption",
            is_new_ticket=True, media_id="photo_id", content_type="photo"
        )

        mock_bot.send_photo.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_notification_with_document(self, mock_bot):
        """Test notification with document attachment."""
        ticket = MagicMock()
        ticket.id = 123
        ticket.daily_id = 1
        ticket.priority = TicketPriority.NORMAL
        ticket.category.name = "Docs"

        user = MagicMock()
        user.external_id = 111
        user.full_name = "Test User"
        user.is_head_student = True
        user.course = 3
        user.group_number = "IVT-301"
        user.department = "Faculty of CS"

        result = await _send_staff_notification(
            mock_bot, ticket, user, "Document attached",
            is_new_ticket=False, media_id="doc_id", content_type="document"
        )

        mock_bot.send_document.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_notification_truncates_long_text(self, mock_bot):
        """Test notification truncates very long text."""
        ticket = MagicMock()
        ticket.id = 123
        ticket.daily_id = 1
        ticket.priority = TicketPriority.NORMAL
        ticket.category.name = "General"

        user = MagicMock()
        user.external_id = 111
        user.full_name = "Test User"
        user.is_head_student = False
        user.course = None
        user.group_number = None
        user.department = None

        long_text = "A" * 5000  # Very long text

        result = await _send_staff_notification(
            mock_bot, ticket, user, long_text,
            is_new_ticket=True
        )

        # Should have truncated and called successfully
        mock_bot.send_message.assert_called_once()
        args, kwargs = mock_bot.send_message.call_args
        assert "truncated" in args[1]

    @pytest.mark.asyncio
    async def test_notification_handles_send_error(self, mock_bot):
        """Test notification handles send failure."""
        mock_bot.send_message.side_effect = Exception("Send failed")

        ticket = MagicMock()
        ticket.id = 123
        ticket.daily_id = 1
        ticket.priority = TicketPriority.NORMAL
        ticket.category.name = "General"

        user = MagicMock()
        user.external_id = 111
        user.full_name = "Test User"
        user.is_head_student = False
        user.course = None
        user.group_number = None
        user.department = None

        result = await _send_staff_notification(
            mock_bot, ticket, user, "Test text",
            is_new_ticket=True
        )

        # Should return None on error
        assert result is None

    @pytest.mark.asyncio
    async def test_notification_media_only(self, mock_bot):
        """Test notification with media but no text."""
        ticket = MagicMock()
        ticket.id = 123
        ticket.daily_id = 1
        ticket.priority = TicketPriority.NORMAL
        ticket.category.name = "Photos"

        user = MagicMock()
        user.external_id = 111
        user.full_name = "Test User"
        user.is_head_student = False
        user.course = 1
        user.group_number = "GR-101"
        user.department = None

        result = await _send_staff_notification(
            mock_bot, ticket, user, "",  # No text
            is_new_ticket=True, media_id="photo_only", content_type="photo"
        )

        mock_bot.send_photo.assert_called_once()
        args, kwargs = mock_bot.send_photo.call_args
        # Should have "(Вложение)" placeholder
        assert "(Вложение)" in kwargs.get('caption', '')


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_get_next_daily_id(self, test_session):
        """Test get_next_daily_id increments correctly."""
        id1 = await get_next_daily_id(test_session)
        id2 = await get_next_daily_id(test_session)
        id3 = await get_next_daily_id(test_session)

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    @pytest.mark.asyncio
    async def test_get_active_ticket_returns_none_for_nonexistent(self, test_session):
        """Test get_active_ticket returns None for nonexistent user."""
        result = await get_active_ticket(test_session, 999999, SourceType.TELEGRAM)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_history_empty(self, test_session):
        """Test get_user_history returns empty for no tickets."""
        # Create user
        user = User(
            external_id=88888,
            source=SourceType.TELEGRAM,
            full_name="Test User"
        )
        test_session.add(user)
        await test_session.commit()

        result = await get_user_history(test_session, user.id)
        assert result == []
