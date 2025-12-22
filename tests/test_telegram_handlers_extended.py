"""Additional tests for telegram handlers to improve coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser, Chat
from database.models import User, Ticket, TicketStatus, Category, SourceType
from handlers.telegram import (
    cmd_start, process_course_callback, process_course_text,
    process_group, process_role, show_faq, back_to_main,
    cmd_myprofile, cmd_updateprofile, process_student_id,
    process_course_update, process_group_update, process_role_update,
    process_department, TicketForm, ProfileForm, Registration,
    select_cat, handle_message_content
)
from core.config import settings


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


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    result_mock = MagicMock()
    session.execute.return_value = result_mock
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_state():
    """Create a mock FSM state."""
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


# =================================
# Registration Flow Tests
# =================================

class TestRegistrationFlow:
    """Tests for registration flow handlers."""

    @pytest.mark.asyncio
    async def test_cmd_start_without_group(self, mock_state, mock_session):
        """Test /start when user has no group (triggers registration)."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.first_name = "TestUser"
        message.from_user.id = 123
        message.from_user.full_name = "TestUser Full"
        message.from_user.username = "testuser"
        message.answer = AsyncMock()

        # Mock UserRepository to return user without group
        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            mock_user = MagicMock()
            mock_user.group_number = None  # No group - triggers registration
            mock_user.full_name = "TestUser Full"
            mock_repo.get_or_create.return_value = mock_user
            MockUserRepository.return_value = mock_repo

            await cmd_start(message, mock_state, mock_session)

            mock_state.clear.assert_called_once()
            mock_state.set_state.assert_called_once_with(Registration.waiting_for_course)
            message.answer.assert_called_once()
            args, kwargs = message.answer.call_args
            assert "На каком ты курсе" in args[0]

    @pytest.mark.asyncio
    async def test_process_course_callback_valid(self, mock_state):
        """Test processing course selection via callback."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "3"  # Course number
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        await process_course_callback(callback, mock_state)

        mock_state.update_data.assert_called_once_with(course=3)
        mock_state.set_state.assert_called_once_with(Registration.waiting_for_group)
        callback.message.edit_text.assert_called_once()
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_course_callback_invalid(self, mock_state):
        """Test processing invalid course callback."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "not_a_number"
        callback.answer = AsyncMock()

        await process_course_callback(callback, mock_state)

        callback.answer.assert_called_once()
        args, kwargs = callback.answer.call_args
        assert "Выберите курс кнопкой" in args[0]
        assert kwargs.get('show_alert') is True
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_course_text_valid(self, mock_state):
        """Test processing course selection via text."""
        message = AsyncMock(spec=Message)
        message.text = "4"
        message.answer = AsyncMock()

        await process_course_text(message, mock_state)

        mock_state.update_data.assert_called_once_with(course=4)
        mock_state.set_state.assert_called_once_with(Registration.waiting_for_group)

    @pytest.mark.asyncio
    async def test_process_course_text_invalid(self, mock_state):
        """Test processing invalid course text."""
        message = AsyncMock(spec=Message)
        message.text = "invalid"
        message.answer = AsyncMock()

        await process_course_text(message, mock_state)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "от 1 до 6" in args[0]
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_course_text_out_of_range(self, mock_state):
        """Test processing out of range course number."""
        message = AsyncMock(spec=Message)
        message.text = "7"  # Out of range
        message.answer = AsyncMock()

        await process_course_text(message, mock_state)

        message.answer.assert_called_once()
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_group_valid(self, mock_state):
        """Test processing group input."""
        message = AsyncMock(spec=Message)
        message.text = "ivt-201"  # Will be uppercased
        message.answer = AsyncMock()

        await process_group(message, mock_state)

        mock_state.update_data.assert_called_once_with(group="IVT-201")
        mock_state.set_state.assert_called_once_with(Registration.waiting_for_role)
        message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_group_too_long(self, mock_state):
        """Test processing group that's too long."""
        message = AsyncMock(spec=Message)
        message.text = "A" * 25  # Too long
        message.answer = AsyncMock()

        await process_group(message, mock_state)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Слишком длинное" in args[0]
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_role_head(self, mock_state, mock_session):
        """Test selecting head student role."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.data = "role_head"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        mock_state.get_data.return_value = {"course": 3, "group": "IVT-301"}

        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            MockUserRepository.return_value = mock_repo

            with patch("handlers.telegram.show_main_menu", new_callable=AsyncMock):
                await process_role(callback, mock_state, mock_session)

            mock_repo.update_profile.assert_called_once_with(
                123, course=3, group="IVT-301", is_head_student=True
            )
            mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_role_student(self, mock_state, mock_session):
        """Test selecting regular student role."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.data = "role_student"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        mock_state.get_data.return_value = {"course": 2, "group": "FIVT-201"}

        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            MockUserRepository.return_value = mock_repo

            with patch("handlers.telegram.show_main_menu", new_callable=AsyncMock):
                await process_role(callback, mock_state, mock_session)

            mock_repo.update_profile.assert_called_once_with(
                123, course=2, group="FIVT-201", is_head_student=False
            )

    @pytest.mark.asyncio
    async def test_process_role_invalid(self, mock_state, mock_session):
        """Test invalid role callback."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "invalid_role"
        callback.answer = AsyncMock()

        await process_role(callback, mock_state, mock_session)

        callback.answer.assert_called_once()


# =================================
# FAQ and Navigation Tests
# =================================

class TestFAQAndNavigation:
    """Tests for FAQ display and navigation."""

    @pytest.mark.asyncio
    async def test_show_faq_with_items(self, mock_session):
        """Test showing FAQ when items exist."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Mock FAQ service
        mock_faq = MagicMock()
        mock_faq.trigger_word = "password"
        mock_faq.answer_text = "Reset it at portal.example.com"

        with patch("handlers.telegram.FAQService") as MockFAQService:
            MockFAQService.get_all_faqs.return_value = [mock_faq]

            await show_faq(callback, mock_session)

        callback.message.edit_text.assert_called_once()
        args, kwargs = callback.message.edit_text.call_args
        assert "FAQ" in args[0]
        assert "password" in args[0]
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_faq_empty(self, mock_session):
        """Test showing FAQ when no items exist."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        with patch("handlers.telegram.FAQService") as MockFAQService:
            MockFAQService.get_all_faqs.return_value = []

            await show_faq(callback, mock_session)

        args, kwargs = callback.message.edit_text.call_args
        assert "пока пуста" in args[0]

    @pytest.mark.asyncio
    async def test_back_to_main(self, mock_state):
        """Test returning to main menu."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.first_name = "TestUser"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        await back_to_main(callback, mock_state)

        mock_state.clear.assert_called_once()
        callback.message.edit_text.assert_called_once()
        args = callback.message.edit_text.call_args[0]
        assert "Привет" in args[0]
        assert "Выберите тему" in args[0]


# =================================
# Profile Commands Tests
# =================================

class TestProfileCommands:
    """Tests for profile-related commands."""

    @pytest.mark.asyncio
    async def test_cmd_myprofile_no_user(self, mock_session):
        """Test /myprofile when user doesn't exist."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await cmd_myprofile(message, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Ваш профиль еще не создан" in args[0]

    @pytest.mark.asyncio
    async def test_cmd_myprofile_with_user(self, mock_session):
        """Test /myprofile with existing user."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.student_id = "12345"
        mock_user.course = 3
        mock_user.group_number = "IVT-301"
        mock_user.is_head_student = True
        mock_user.department = "Computer Science"

        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        await cmd_myprofile(message, mock_session)

        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "Ваш профиль" in args[0]
        assert "Test User" in args[0]
        assert "IVT-301" in args[0]
        assert "Староста" in args[0]
        assert kwargs.get('parse_mode') == "HTML"

    @pytest.mark.asyncio
    async def test_cmd_myprofile_partial_data(self, mock_session):
        """Test /myprofile with partially filled user data."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.student_id = None  # Not set
        mock_user.course = None  # Not set
        mock_user.group_number = None  # Not set
        mock_user.is_head_student = False
        mock_user.department = None  # Not set

        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        await cmd_myprofile(message, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "не указан" in args[0]

    @pytest.mark.asyncio
    async def test_cmd_updateprofile_no_user(self, mock_state, mock_session):
        """Test /updateprofile when user doesn't exist."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        await cmd_updateprofile(message, mock_state, mock_session)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Ваш профиль еще не создан" in args[0]

    @pytest.mark.asyncio
    async def test_cmd_updateprofile_success(self, mock_state, mock_session):
        """Test /updateprofile starts profile update flow."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.answer = AsyncMock()

        mock_user = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        await cmd_updateprofile(message, mock_state, mock_session)

        mock_state.set_state.assert_called_once_with(ProfileForm.waiting_student_id)
        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Обновление профиля" in args[0]

    @pytest.mark.asyncio
    async def test_process_student_id(self, mock_state):
        """Test processing student ID input."""
        message = AsyncMock(spec=Message)
        message.text = "12345678"
        message.answer = AsyncMock()

        await process_student_id(message, mock_state)

        mock_state.update_data.assert_called_once_with(student_id="12345678")
        mock_state.set_state.assert_called_once_with(ProfileForm.waiting_course)

    @pytest.mark.asyncio
    async def test_process_student_id_skip(self, mock_state):
        """Test skipping student ID."""
        message = AsyncMock(spec=Message)
        message.text = "-"
        message.answer = AsyncMock()

        await process_student_id(message, mock_state)

        mock_state.update_data.assert_called_once_with(student_id=None)

    @pytest.mark.asyncio
    async def test_process_course_update_valid(self, mock_state):
        """Test valid course update."""
        message = AsyncMock(spec=Message)
        message.text = "4"
        message.answer = AsyncMock()

        await process_course_update(message, mock_state)

        mock_state.update_data.assert_called_once_with(course=4)
        mock_state.set_state.assert_called_once_with(ProfileForm.waiting_group)

    @pytest.mark.asyncio
    async def test_process_course_update_skip(self, mock_state):
        """Test skipping course update."""
        message = AsyncMock(spec=Message)
        message.text = "-"
        message.answer = AsyncMock()

        await process_course_update(message, mock_state)

        mock_state.update_data.assert_called_once_with(course=None)

    @pytest.mark.asyncio
    async def test_process_course_update_invalid(self, mock_state):
        """Test invalid course number."""
        message = AsyncMock(spec=Message)
        message.text = "7"  # Out of range
        message.answer = AsyncMock()

        await process_course_update(message, mock_state)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "от 1 до 6" in args[0]
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_course_update_non_numeric(self, mock_state):
        """Test non-numeric course input."""
        message = AsyncMock(spec=Message)
        message.text = "abc"
        message.answer = AsyncMock()

        await process_course_update(message, mock_state)

        message.answer.assert_called_once()
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_group_update_valid(self, mock_state):
        """Test valid group update."""
        message = AsyncMock(spec=Message)
        message.text = "cs-301"
        message.answer = AsyncMock()

        await process_group_update(message, mock_state)

        mock_state.update_data.assert_called_once_with(group="CS-301")
        mock_state.set_state.assert_called_once_with(ProfileForm.waiting_role)

    @pytest.mark.asyncio
    async def test_process_group_update_skip(self, mock_state):
        """Test skipping group update."""
        message = AsyncMock(spec=Message)
        message.text = "-"
        message.answer = AsyncMock()

        await process_group_update(message, mock_state)

        mock_state.update_data.assert_called_once_with(group=None)

    @pytest.mark.asyncio
    async def test_process_group_update_too_long(self, mock_state):
        """Test group name too long."""
        message = AsyncMock(spec=Message)
        message.text = "A" * 25
        message.answer = AsyncMock()

        await process_group_update(message, mock_state)

        message.answer.assert_called_once()
        args = message.answer.call_args[0]
        assert "Слишком длинное" in args[0]
        mock_state.update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_role_update_head(self, mock_state, mock_session):
        """Test selecting head role during profile update."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "role_head"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        await process_role_update(callback, mock_state, mock_session)

        mock_state.update_data.assert_called_once_with(is_head=True)
        mock_state.set_state.assert_called_once_with(ProfileForm.waiting_department)

    @pytest.mark.asyncio
    async def test_process_role_update_student(self, mock_state, mock_session):
        """Test selecting student role during profile update."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "role_student"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        await process_role_update(callback, mock_state, mock_session)

        mock_state.update_data.assert_called_once_with(is_head=False)

    @pytest.mark.asyncio
    async def test_process_role_update_skip(self, mock_state, mock_session):
        """Test skipping role selection."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.data = "role_skip"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        await process_role_update(callback, mock_state, mock_session)

        mock_state.update_data.assert_called_once_with(is_head=None)

    @pytest.mark.asyncio
    async def test_process_department_success(self, mock_state, mock_session):
        """Test successful department update."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.text = "Faculty of CS"
        message.answer = AsyncMock()

        mock_state.get_data.return_value = {
            "student_id": "12345",
            "course": 3,
            "group": "CS-301",
            "is_head": True
        }

        mock_user = MagicMock()
        mock_user.course = 2  # Old values
        mock_user.group_number = "OLD"

        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            mock_repo.get_by_external_id.return_value = mock_user
            MockUserRepository.return_value = mock_repo

            await process_department(message, mock_state, mock_session)

        assert mock_user.course == 3
        assert mock_user.group_number == "CS-301"
        assert mock_user.is_head_student is True
        assert mock_user.department == "Faculty of CS"
        assert mock_user.student_id == "12345"
        mock_session.commit.assert_called_once()
        mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_department_skip(self, mock_state, mock_session):
        """Test skipping department input."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.text = "-"
        message.answer = AsyncMock()

        mock_state.get_data.return_value = {
            "student_id": "12345",
            "course": None,
            "group": None,
            "is_head": None
        }

        mock_user = MagicMock()

        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            mock_repo.get_by_external_id.return_value = mock_user
            MockUserRepository.return_value = mock_repo

            await process_department(message, mock_state, mock_session)

        assert mock_user.department is None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_department_user_not_found(self, mock_state, mock_session):
        """Test department update when user not found."""
        message = AsyncMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.text = "Faculty of CS"
        message.answer = AsyncMock()

        mock_state.get_data.return_value = {}

        with patch("handlers.telegram.UserRepository") as MockUserRepository:
            mock_repo = AsyncMock()
            mock_repo.get_by_external_id.return_value = None
            MockUserRepository.return_value = mock_repo

            await process_department(message, mock_state, mock_session)

        message.answer.assert_called()
        args = message.answer.call_args[0]
        assert "Ошибка" in args[0]


# =================================
# Category Selection with Saved Text
# =================================

class TestCategorySelectionWithSavedText:
    """Tests for category selection with pre-saved text."""

    @pytest.mark.asyncio
    async def test_select_cat_with_saved_text(self, mock_session, mock_state, mock_bot):
        """Test selecting category when text was already saved."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.from_user.full_name = "Test User"
        callback.data = "cat_study"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Text was saved in state
        mock_state.get_data.return_value = {
            "saved_text": "My pre-saved question"
        }

        with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = None

            with patch("handlers.telegram.create_ticket", new_callable=AsyncMock) as mock_create:
                mock_ticket = MagicMock()
                mock_ticket.daily_id = 42
                mock_create.return_value = mock_ticket

                await select_cat(callback, mock_state, mock_session, mock_bot)

                mock_create.assert_called_once()
                args, kwargs = mock_create.call_args
                assert "My pre-saved question" in args

                callback.message.edit_text.assert_called_once()
                msg_args = callback.message.edit_text.call_args[0]
                assert "#42" in msg_args[0]
                mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_cat_with_saved_media(self, mock_session, mock_state, mock_bot):
        """Test selecting category when media was saved."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123
        callback.from_user.full_name = "Test User"
        callback.data = "cat_docs"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        # Media was saved in state
        mock_state.get_data.return_value = {
            "saved_media": {
                "media_id": "photo123",
                "content_type": "photo"
            }
        }

        with patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = None

            with patch("handlers.telegram.create_ticket", new_callable=AsyncMock) as mock_create:
                mock_ticket = MagicMock()
                mock_ticket.daily_id = 43
                mock_create.return_value = mock_ticket

                await select_cat(callback, mock_state, mock_session, mock_bot)

                mock_create.assert_called_once()
                args, kwargs = mock_create.call_args
                assert kwargs.get('media_id') == "photo123"
                assert kwargs.get('content_type') == "photo"


# =================================
# Message Content Handling Tests
# =================================

class TestMessageContentHandling:
    """Tests for various message content types."""

    @pytest.mark.asyncio
    async def test_handle_message_photo(self, mock_session, mock_state, mock_bot):
        """Test handling photo message."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 12345
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.from_user.full_name = "User"
        message.text = None
        message.caption = "Photo caption"
        message.answer = AsyncMock()
        message.document = None

        # Mock photo with file_id
        photo = MagicMock()
        photo.file_id = "photo_file_id_123"
        message.photo = [photo]

        # User has active ticket
        mock_ticket = MagicMock()

        with patch("handlers.telegram.FAQService") as MockFAQService, \
             patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active, \
             patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg:

            MockFAQService.find_match.return_value = None
            mock_get_active.return_value = mock_ticket

            await handle_message_content(message, mock_state, mock_bot, mock_session)

            mock_add_msg.assert_called_once()
            args, kwargs = mock_add_msg.call_args
            assert kwargs.get('media_id') == "photo_file_id_123"
            assert kwargs.get('content_type') == "photo"

    @pytest.mark.asyncio
    async def test_handle_message_document(self, mock_session, mock_state, mock_bot):
        """Test handling document message."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 12345
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.from_user.full_name = "User"
        message.text = None
        message.caption = "Document caption"
        message.answer = AsyncMock()
        message.photo = None

        # Mock document with file_id
        document = MagicMock()
        document.file_id = "document_file_id_456"
        message.document = document

        # User has active ticket
        mock_ticket = MagicMock()

        with patch("handlers.telegram.FAQService") as MockFAQService, \
             patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active, \
             patch("handlers.telegram.add_message_to_ticket", new_callable=AsyncMock) as mock_add_msg:

            MockFAQService.find_match.return_value = None
            mock_get_active.return_value = mock_ticket

            await handle_message_content(message, mock_state, mock_bot, mock_session)

            mock_add_msg.assert_called_once()
            args, kwargs = mock_add_msg.call_args
            assert kwargs.get('media_id') == "document_file_id_456"
            assert kwargs.get('content_type') == "document"

    @pytest.mark.asyncio
    async def test_handle_message_faq_match(self, mock_session, mock_state, mock_bot):
        """Test handling message that matches FAQ."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 12345
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.text = "How do I reset my password?"
        message.photo = None
        message.document = None
        message.answer = AsyncMock()

        mock_faq = MagicMock()
        mock_faq.answer_text = "Go to portal.example.com and click 'Forgot Password'"

        with patch("handlers.telegram.FAQService") as MockFAQService:
            MockFAQService.find_match.return_value = mock_faq

            await handle_message_content(message, mock_state, mock_bot, mock_session)

            message.answer.assert_called_once()
            args, kwargs = message.answer.call_args
            assert "Подсказка" in args[0]
            assert "portal.example.com" in args[0]

    @pytest.mark.asyncio
    async def test_handle_message_during_registration(self, mock_session, mock_state, mock_bot):
        """Test that registration states are skipped for text messages."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 12345
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123
        message.text = "Some text"
        message.photo = None
        message.document = None
        message.answer = AsyncMock()

        # User is in registration state
        mock_state.get_state.return_value = Registration.waiting_for_course

        with patch("handlers.telegram.FAQService") as MockFAQService, \
             patch("handlers.telegram.get_active_ticket", new_callable=AsyncMock) as mock_get_active:

            MockFAQService.find_match.return_value = None
            mock_get_active.return_value = None

            await handle_message_content(message, mock_state, mock_bot, mock_session)

            # Should return early and not answer
            # (the specific registration handler should handle it)
            # Due to return statement, answer should not be called for main flow
