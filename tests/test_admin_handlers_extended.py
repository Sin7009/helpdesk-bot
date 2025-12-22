"""Extended tests for admin handlers to improve coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.filters import CommandObject
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat, ReactionTypeEmoji
from handlers.admin import (
    admin_reply_native,
    admin_close_ticket,
    close_ticket_btn,
    process_reply,
    handle_rating,
    is_admin_or_mod,
    is_root_admin
)
from database.models import User, UserRole, Ticket, TicketStatus, Category, Message as DbMessage
from core.config import settings


@pytest.fixture
def mock_bot():
    """Create a mock bot."""
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(id=999)
    mock_message = MagicMock()
    mock_message.message_id = 12345
    bot.send_message.return_value = mock_message
    bot.send_photo.return_value = mock_message
    bot.send_document.return_value = mock_message
    return bot


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    session.add = MagicMock()
    return session


class TestAccessControl:
    """Tests for admin access control functions."""

    @pytest.mark.asyncio
    async def test_is_admin_or_mod_root_admin(self, mock_session):
        """Test is_admin_or_mod returns True for root admin."""
        result = await is_admin_or_mod(settings.TG_ADMIN_ID, mock_session)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_or_mod_db_admin(self, mock_session):
        """Test is_admin_or_mod returns True for DB admin."""
        mock_user = MagicMock()
        mock_user.role = UserRole.ADMIN
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        result = await is_admin_or_mod(99999, mock_session)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_or_mod_moderator(self, mock_session):
        """Test is_admin_or_mod returns True for moderator."""
        mock_user = MagicMock()
        mock_user.role = UserRole.MODERATOR
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        result = await is_admin_or_mod(99999, mock_session)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_or_mod_regular_user(self, mock_session):
        """Test is_admin_or_mod returns False for regular user."""
        mock_user = MagicMock()
        mock_user.role = UserRole.USER
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        result = await is_admin_or_mod(99999, mock_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_admin_or_mod_no_user(self, mock_session):
        """Test is_admin_or_mod returns False when user not found."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = await is_admin_or_mod(99999, mock_session)
        # Returns None when user not found (which is falsy)
        assert not result

    @pytest.mark.asyncio
    async def test_is_root_admin_true(self):
        """Test is_root_admin returns True for root admin."""
        result = await is_root_admin(settings.TG_ADMIN_ID)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_root_admin_false(self):
        """Test is_root_admin returns False for non-root admin."""
        result = await is_root_admin(99999)
        assert result is False


class TestAdminReplyNative:
    """Tests for admin_reply_native handler."""

    @pytest.mark.asyncio
    async def test_reply_native_non_admin(self, mock_bot, mock_session):
        """Test non-admin user cannot reply."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 99999  # Not admin
        message.reply_to_message = AsyncMock(spec=Message)
        message.reply_to_message.from_user = MagicMock(spec=TgUser)
        message.reply_to_message.from_user.id = 999  # Bot

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await admin_reply_native(message, mock_bot, mock_session)

        # No action taken
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_reply_native_with_photo(self, mock_bot, mock_session):
        """Test admin reply with photo attachment."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.reply_to_message = AsyncMock(spec=Message)
        message.reply_to_message.from_user = MagicMock(spec=TgUser)
        message.reply_to_message.from_user.id = 999  # Bot
        message.reply_to_message.text = "ID: #123"
        message.reply_to_message.message_id = 54321
        message.text = None
        message.caption = "Photo reply"
        message.document = None

        # Mock photo
        photo = MagicMock()
        photo.file_id = "photo_reply_id"
        message.photo = [photo]

        # Mock ticket
        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        with patch("handlers.admin.TicketRepository") as MockTicketRepo, \
             patch("handlers.admin.process_reply", new_callable=AsyncMock) as mock_process:
            mock_repo = AsyncMock()
            mock_repo.get_by_admin_message_id.return_value = ticket
            MockTicketRepo.return_value = mock_repo

            await admin_reply_native(message, mock_bot, mock_session)

            mock_process.assert_called_once()
            args, kwargs = mock_process.call_args
            assert kwargs.get('media_id') == "photo_reply_id"
            assert kwargs.get('content_type') == "photo"

    @pytest.mark.asyncio
    async def test_reply_native_with_document(self, mock_bot, mock_session):
        """Test admin reply with document attachment."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.reply_to_message = AsyncMock(spec=Message)
        message.reply_to_message.from_user = MagicMock(spec=TgUser)
        message.reply_to_message.from_user.id = 999  # Bot
        message.reply_to_message.text = "ID: #123"
        message.reply_to_message.message_id = 54321
        message.text = None
        message.caption = "Document reply"
        message.photo = None

        # Mock document
        doc = MagicMock()
        doc.file_id = "doc_reply_id"
        message.document = doc

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        with patch("handlers.admin.TicketRepository") as MockTicketRepo, \
             patch("handlers.admin.process_reply", new_callable=AsyncMock) as mock_process:
            mock_repo = AsyncMock()
            mock_repo.get_by_admin_message_id.return_value = ticket
            MockTicketRepo.return_value = mock_repo

            await admin_reply_native(message, mock_bot, mock_session)

            mock_process.assert_called_once()
            args, kwargs = mock_process.call_args
            assert kwargs.get('media_id') == "doc_reply_id"
            assert kwargs.get('content_type') == "document"

    @pytest.mark.asyncio
    async def test_reply_native_empty_text(self, mock_bot, mock_session):
        """Test admin reply with empty text is rejected."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.reply_to_message = AsyncMock(spec=Message)
        message.reply_to_message.from_user = MagicMock(spec=TgUser)
        message.reply_to_message.from_user.id = 999  # Bot
        message.reply_to_message.text = "ID: #123"
        message.reply_to_message.message_id = 54321
        message.text = "   "  # Empty/whitespace
        message.caption = None
        message.photo = None
        message.document = None
        message.answer = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123

        with patch("handlers.admin.TicketRepository") as MockTicketRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_admin_message_id.return_value = ticket
            MockTicketRepo.return_value = mock_repo

            await admin_reply_native(message, mock_bot, mock_session)

            message.answer.assert_called_once()
            args = message.answer.call_args[0]
            assert "не может быть пустым" in args[0]

    @pytest.mark.asyncio
    async def test_reply_native_fallback_regex(self, mock_bot, mock_session):
        """Test fallback to regex parsing when message_id lookup fails."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.reply_to_message = AsyncMock(spec=Message)
        message.reply_to_message.from_user = MagicMock(spec=TgUser)
        message.reply_to_message.from_user.id = 999  # Bot
        message.reply_to_message.text = "Ticket #456 - some text"  # Old format
        message.reply_to_message.message_id = 99999
        message.reply_to_message.caption = None
        message.text = "Reply text"
        message.photo = None
        message.document = None

        ticket = MagicMock(spec=Ticket)
        ticket.id = 456
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111

        with patch("handlers.admin.TicketRepository") as MockTicketRepo, \
             patch("handlers.admin.process_reply", new_callable=AsyncMock) as mock_process:
            mock_repo = AsyncMock()
            mock_repo.get_by_admin_message_id.return_value = None  # Not found by ID
            MockTicketRepo.return_value = mock_repo

            # Fallback regex finds ticket
            mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

            await admin_reply_native(message, mock_bot, mock_session)

            mock_process.assert_called_once()


class TestAdminCloseTicket:
    """Tests for admin_close_ticket handler."""

    @pytest.mark.asyncio
    async def test_close_ticket_no_args(self, mock_bot, mock_session):
        """Test close ticket without ticket ID."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="close", args="")

        await admin_close_ticket(message, command, mock_bot, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Формат: /close ID" in args[0]

    @pytest.mark.asyncio
    async def test_close_ticket_invalid_id(self, mock_bot, mock_session):
        """Test close ticket with invalid ID."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="close", args="abc")

        await admin_close_ticket(message, command, mock_bot, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Формат: /close ID" in args[0]

    @pytest.mark.asyncio
    async def test_close_ticket_not_found(self, mock_bot, mock_session):
        """Test close ticket when not found."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="close", args="999")

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await admin_close_ticket(message, command, mock_bot, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "не найден" in args[0]

    @pytest.mark.asyncio
    async def test_close_ticket_already_closed(self, mock_bot, mock_session):
        """Test closing already closed ticket."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="close", args="123")

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.CLOSED
        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await admin_close_ticket(message, command, mock_bot, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "закрыт" in args[0]

    @pytest.mark.asyncio
    async def test_close_ticket_generates_summary(self, mock_bot, mock_session):
        """Test closing ticket generates summary."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="close", args="123")

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.user.external_id = 111
        ticket.summary = None

        # Mock messages for summary generation
        mock_messages = [MagicMock(), MagicMock()]

        # First execute returns ticket, second returns messages
        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_messages

        with patch("handlers.admin.LLMService") as MockLLMService:
            MockLLMService.format_dialogue.return_value = "dialogue text"
            MockLLMService.generate_summary = AsyncMock(return_value="Summary text")

            await admin_close_ticket(message, command, mock_bot, mock_session)

            MockLLMService.generate_summary.assert_called_once()
            assert ticket.summary == "Summary text"
            assert ticket.status == TicketStatus.CLOSED


class TestProcessReply:
    """Tests for process_reply function."""

    @pytest.mark.asyncio
    async def test_process_reply_with_photo(self, mock_bot, mock_session):
        """Test reply with photo attachment."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()
        message.react = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111
        ticket.first_response_at = None

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await process_reply(
            mock_bot, mock_session, 123, "Photo caption", message,
            close=False, ticket_obj=ticket,
            media_id="photo_id", content_type="photo"
        )

        mock_bot.send_photo.assert_called_once()
        args, kwargs = mock_bot.send_photo.call_args
        # Verify the key parameters were passed correctly
        assert args[0] == 111  # user.external_id
        assert kwargs.get('photo') == "photo_id"
        assert "Photo caption" in kwargs.get('caption', '')

    @pytest.mark.asyncio
    async def test_process_reply_with_document(self, mock_bot, mock_session):
        """Test reply with document attachment."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()
        message.react = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111
        ticket.first_response_at = None

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await process_reply(
            mock_bot, mock_session, 123, "Doc caption", message,
            close=False, ticket_obj=ticket,
            media_id="doc_id", content_type="document"
        )

        mock_bot.send_document.assert_called_once()
        args, kwargs = mock_bot.send_document.call_args
        # Verify the key parameters were passed correctly
        assert args[0] == 111  # user.external_id
        assert kwargs.get('document') == "doc_id"

    @pytest.mark.asyncio
    async def test_process_reply_empty_text_without_media(self, mock_bot, mock_session):
        """Test reply with empty text and no media is rejected."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        await process_reply(
            mock_bot, mock_session, 123, "", message,
            close=False, ticket_obj=None,
            media_id=None, content_type="text"
        )

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "не может быть пустым" in args[0]

    @pytest.mark.asyncio
    async def test_process_reply_ticket_not_found(self, mock_bot, mock_session):
        """Test reply when ticket not found."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await process_reply(
            mock_bot, mock_session, 999, "Reply text", message,
            close=False, ticket_obj=None
        )

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "не найден" in args[0]

    @pytest.mark.asyncio
    async def test_process_reply_to_closed_ticket(self, mock_bot, mock_session):
        """Test reply to already closed ticket."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.CLOSED

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await process_reply(
            mock_bot, mock_session, 123, "Reply text", message,
            close=False
        )

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "уже закрыт" in args[0]

    @pytest.mark.asyncio
    async def test_process_reply_sets_first_response_time(self, mock_bot, mock_session):
        """Test reply sets first_response_at when not set."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()
        message.react = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111
        ticket.first_response_at = None

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await process_reply(
            mock_bot, mock_session, 123, "First reply", message,
            close=False, ticket_obj=ticket
        )

        # first_response_at should be set
        assert ticket.first_response_at is not None

    @pytest.mark.asyncio
    async def test_process_reply_send_failure(self, mock_bot, mock_session):
        """Test reply handles send failure gracefully."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.user.external_id = 111

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket
        mock_bot.send_message.side_effect = Exception("Send failed")

        await process_reply(
            mock_bot, mock_session, 123, "Reply text", message,
            close=False, ticket_obj=ticket
        )

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Ошибка отправки" in args[0]


class TestCloseTicketButton:
    """Tests for close_ticket_btn handler."""

    @pytest.mark.asyncio
    async def test_close_ticket_btn_with_caption(self, mock_bot):
        """Test closing ticket when message has caption (media)."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = settings.TG_ADMIN_ID
        callback.data = "close_123"
        callback.message = AsyncMock()
        callback.message.text = None  # No text
        callback.message.caption = "Photo caption"
        callback.message.edit_reply_markup = AsyncMock()
        callback.message.reply = AsyncMock()
        callback.answer = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.user.external_id = 111

        mock_session = AsyncMock()
        result_mock = MagicMock()
        mock_session.execute.return_value = result_mock
        result_mock.scalar_one_or_none.return_value = ticket
        result_mock.scalars.return_value.all.return_value = []  # No messages

        with patch("handlers.admin.new_session", return_value=mock_session):
            mock_session.__aenter__.return_value = mock_session

            await close_ticket_btn(callback, mock_bot)

            callback.message.edit_reply_markup.assert_called_once()
            callback.message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_ticket_btn_no_text_no_caption(self, mock_bot):
        """Test closing ticket when message has no text or caption."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = settings.TG_ADMIN_ID
        callback.data = "close_123"
        callback.message = AsyncMock()
        callback.message.text = None
        callback.message.caption = None
        callback.message.answer = AsyncMock()
        callback.message.edit_reply_markup = AsyncMock()
        callback.answer = AsyncMock()

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.user.external_id = 111

        mock_session = AsyncMock()
        result_mock = MagicMock()
        mock_session.execute.return_value = result_mock
        result_mock.scalar_one_or_none.return_value = ticket
        result_mock.scalars.return_value.all.return_value = []

        with patch("handlers.admin.new_session", return_value=mock_session):
            mock_session.__aenter__.return_value = mock_session

            await close_ticket_btn(callback, mock_bot)

            callback.message.answer.assert_called_once()


class TestHandleRatingExtended:
    """Extended tests for handle_rating."""

    @pytest.mark.asyncio
    async def test_handle_rating_invalid_format(self, mock_bot):
        """Test rating with invalid format."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "rate_invalid"  # Wrong format
        callback.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch("handlers.admin.new_session", return_value=mock_session_ctx):
            await handle_rating(callback, mock_bot)

            callback.answer.assert_called_once()
            args = callback.answer.call_args[0]
            assert "Ошибка" in args[0]

    @pytest.mark.asyncio
    async def test_handle_rating_out_of_range(self, mock_bot):
        """Test rating with value out of range."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "rate_123_6"  # Rating 6 is out of range
        callback.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch("handlers.admin.new_session", return_value=mock_session_ctx):
            await handle_rating(callback, mock_bot)

            callback.answer.assert_called_once()
            args = callback.answer.call_args[0]
            assert "Неверная оценка" in args[0]


class TestAssignTicketCommand:
    """Tests for assign_ticket_cmd handler."""

    @pytest.mark.asyncio
    async def test_assign_ticket_no_args(self, mock_session):
        """Test assign command without arguments."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args=None)

        await assign_ticket_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "Формат" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_insufficient_args(self, mock_session):
        """Test assign command with only ticket ID."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123")

        await assign_ticket_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "Недостаточно аргументов" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_invalid_id(self, mock_session):
        """Test assign command with non-numeric ticket ID."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="abc @moderator")

        await assign_ticket_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "числом" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_not_found(self, mock_session):
        """Test assign command when ticket doesn't exist."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="999 @moderator")

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await assign_ticket_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "не найден" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_already_closed(self, mock_session):
        """Test assign command on closed ticket."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123 @moderator")

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.CLOSED

        mock_session.execute.return_value.scalar_one_or_none.return_value = ticket

        await assign_ticket_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "закрыт" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_staff_not_found(self, mock_session):
        """Test assign command when staff member doesn't exist."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123 @unknown_user")

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW

        # First call returns ticket, second call returns None (staff not found)
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [ticket, None]

        await assign_ticket_cmd(message, command, mock_session)

        assert message.answer.call_count == 1
        args = message.answer.call_args[0]
        assert "не найден" in args[0] or "не является модератором" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_success(self, mock_session):
        """Test successful ticket assignment."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123 @moderator")

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.NEW
        ticket.assigned_staff = None

        staff = MagicMock(spec=User)
        staff.id = 456
        staff.username = "moderator"
        staff.role = UserRole.MODERATOR

        # First call returns ticket, second call returns staff
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [ticket, staff]

        await assign_ticket_cmd(message, command, mock_session)

        assert ticket.assigned_to == 456
        assert ticket.status == TicketStatus.IN_PROGRESS
        mock_session.commit.assert_called_once()
        
        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "назначен" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_reassign(self, mock_session):
        """Test reassigning ticket from one staff to another."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123 @new_mod")

        old_staff = MagicMock(spec=User)
        old_staff.username = "old_mod"

        ticket = MagicMock(spec=Ticket)
        ticket.id = 123
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.assigned_staff = old_staff

        new_staff = MagicMock(spec=User)
        new_staff.id = 789
        new_staff.username = "new_mod"
        new_staff.role = UserRole.MODERATOR

        # First call returns ticket, second call returns staff
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [ticket, new_staff]

        await assign_ticket_cmd(message, command, mock_session)

        assert ticket.assigned_to == 789
        mock_session.commit.assert_called_once()
        
        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "переназначен" in args[0]

    @pytest.mark.asyncio
    async def test_assign_ticket_non_admin(self, mock_session):
        """Test non-admin cannot assign tickets."""
        from handlers.admin import assign_ticket_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 99999  # Not admin
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="assign", args="123 @moderator")

        # Return regular user
        regular_user = MagicMock(spec=User)
        regular_user.role = UserRole.USER
        mock_session.execute.return_value.scalar_one_or_none.return_value = regular_user

        await assign_ticket_cmd(message, command, mock_session)

        # Should not proceed - no message sent
        message.answer.assert_not_called()


class TestExportStatisticsCommand:
    """Tests for export_statistics_cmd handler."""

    @pytest.mark.asyncio
    async def test_export_no_permission(self, mock_session):
        """Test non-admin cannot export."""
        from handlers.admin import export_statistics_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 99999  # Not admin
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="export", args=None)

        # Return regular user
        regular_user = MagicMock(spec=User)
        regular_user.role = UserRole.USER
        mock_session.execute.return_value.scalar_one_or_none.return_value = regular_user

        await export_statistics_cmd(message, command, mock_session)

        # Should not proceed
        message.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_invalid_days(self, mock_session):
        """Test export with invalid days argument."""
        from handlers.admin import export_statistics_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="export", args="abc")

        await export_statistics_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "число" in args[0]

    @pytest.mark.asyncio
    async def test_export_days_out_of_range(self, mock_session):
        """Test export with days out of range."""
        from handlers.admin import export_statistics_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="export", args="500")

        await export_statistics_cmd(message, command, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "365" in args[0]

    @pytest.mark.asyncio
    async def test_export_no_tickets(self, mock_session):
        """Test export when no tickets exist."""
        from handlers.admin import export_statistics_cmd
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()

        command = CommandObject(prefix="/", command="export", args="7")

        # Return empty list
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        await export_statistics_cmd(message, command, mock_session)

        # Should show generating message then no tickets message
        assert message.answer.call_count == 2
        last_call = message.answer.call_args_list[-1]
        assert "Нет тикетов" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_export_success(self, mock_session):
        """Test successful export with tickets."""
        from handlers.admin import export_statistics_cmd
        import datetime
        
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = settings.TG_ADMIN_ID
        message.answer = AsyncMock()
        message.answer_document = AsyncMock()

        command = CommandObject(prefix="/", command="export", args="30")

        # Create mock ticket
        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.external_id = 123

        mock_category = MagicMock()
        mock_category.name = "IT"

        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = 1
        mock_ticket.daily_id = 1
        mock_ticket.created_at = datetime.datetime.now()
        mock_ticket.closed_at = None
        mock_ticket.status = TicketStatus.NEW
        mock_ticket.priority = MagicMock()
        mock_ticket.priority.value = "normal"
        mock_ticket.category = mock_category
        mock_ticket.user = mock_user
        mock_ticket.assigned_staff = None
        mock_ticket.first_response_at = None
        mock_ticket.rating = None
        mock_ticket.question_text = "Test question"

        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_ticket]

        await export_statistics_cmd(message, command, mock_session)

        # Should send document
        message.answer_document.assert_called_once()
        args, kwargs = message.answer_document.call_args
        assert "Экспорт" in kwargs.get('caption', '')
