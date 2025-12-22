"""Tests for database repositories."""
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from database.models import (
    Base, User, Ticket, TicketStatus, SourceType, Category, DailyTicketCounter
)
from database.repositories.base import BaseRepository
from database.repositories.user_repository import UserRepository
from database.repositories.ticket_repository import TicketRepository

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


# =============================
# BaseRepository Tests
# =============================

class TestBaseRepository:
    """Tests for BaseRepository class."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, test_session):
        """Test get_by_id returns entity when found."""
        # Create a user
        user = User(
            external_id=12345,
            source=SourceType.TELEGRAM,
            full_name="Test User"
        )
        test_session.add(user)
        await test_session.commit()

        repo = BaseRepository(test_session, User)
        result = await repo.get_by_id(user.id)

        assert result is not None
        assert result.external_id == 12345
        assert result.full_name == "Test User"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_session):
        """Test get_by_id returns None when not found."""
        repo = BaseRepository(test_session, User)
        result = await repo.get_by_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_add_entity(self, test_session):
        """Test add method adds entity to session."""
        repo = BaseRepository(test_session, User)
        user = User(
            external_id=54321,
            source=SourceType.TELEGRAM,
            full_name="New User"
        )

        repo.add(user)
        await test_session.flush()

        assert user.id is not None

    @pytest.mark.asyncio
    async def test_flush(self, test_session):
        """Test flush persists changes."""
        repo = BaseRepository(test_session, User)
        user = User(
            external_id=11111,
            source=SourceType.TELEGRAM,
            full_name="Flush Test"
        )
        test_session.add(user)

        await repo.flush()

        assert user.id is not None

    @pytest.mark.asyncio
    async def test_commit(self, test_session):
        """Test commit persists changes."""
        repo = BaseRepository(test_session, User)
        user = User(
            external_id=22222,
            source=SourceType.TELEGRAM,
            full_name="Commit Test"
        )
        test_session.add(user)

        await repo.commit()

        # Re-query to verify commit
        result = await test_session.get(User, user.id)
        assert result is not None


# =============================
# UserRepository Tests
# =============================

class TestUserRepository:
    """Tests for UserRepository class."""

    @pytest.fixture
    def mock_tg_user(self):
        """Create a mock Telegram user object."""
        mock_user = MagicMock()
        mock_user.id = 123456
        mock_user.username = "testuser"
        mock_user.full_name = "Test Full Name"
        return mock_user

    @pytest.mark.asyncio
    async def test_get_by_external_id_found(self, test_session):
        """Test get_by_external_id returns user when found."""
        # Create a user
        user = User(
            external_id=111222,
            source=SourceType.TELEGRAM,
            full_name="External ID Test"
        )
        test_session.add(user)
        await test_session.commit()

        repo = UserRepository(test_session)
        result = await repo.get_by_external_id(111222, SourceType.TELEGRAM)

        assert result is not None
        assert result.external_id == 111222

    @pytest.mark.asyncio
    async def test_get_by_external_id_not_found(self, test_session):
        """Test get_by_external_id returns None when not found."""
        repo = UserRepository(test_session)
        result = await repo.get_by_external_id(99999999, SourceType.TELEGRAM)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new(self, test_session, mock_tg_user):
        """Test get_or_create creates new user when not exists."""
        repo = UserRepository(test_session)
        result = await repo.get_or_create(mock_tg_user)

        assert result is not None
        assert result.external_id == 123456
        assert result.username == "testuser"
        assert result.full_name == "Test Full Name"
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self, test_session, mock_tg_user):
        """Test get_or_create returns existing user."""
        # Create user first
        user = User(
            external_id=123456,
            source=SourceType.TELEGRAM,
            username="oldusername",
            full_name="Old Name"
        )
        test_session.add(user)
        await test_session.commit()

        repo = UserRepository(test_session)
        result = await repo.get_or_create(mock_tg_user)

        assert result.id == user.id
        # Username and full_name should be updated
        assert result.username == "testuser"
        assert result.full_name == "Test Full Name"

    @pytest.mark.asyncio
    async def test_get_or_create_updates_info_if_changed(self, test_session):
        """Test get_or_create updates user info when changed."""
        # Create user with old info
        user = User(
            external_id=999888,
            source=SourceType.TELEGRAM,
            username="old_username",
            full_name="Old Name"
        )
        test_session.add(user)
        await test_session.commit()
        old_id = user.id

        # Mock new user with updated info
        mock_user = MagicMock()
        mock_user.id = 999888
        mock_user.username = "new_username"
        mock_user.full_name = "New Name"

        repo = UserRepository(test_session)
        result = await repo.get_or_create(mock_user)

        assert result.id == old_id
        assert result.username == "new_username"
        assert result.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_update_profile_success(self, test_session):
        """Test update_profile updates user fields."""
        # Create user
        user = User(
            external_id=333444,
            source=SourceType.TELEGRAM,
            full_name="Profile Test"
        )
        test_session.add(user)
        await test_session.commit()

        repo = UserRepository(test_session)
        result = await repo.update_profile(
            external_id=333444,
            course=3,
            group="CS-301",
            is_head_student=True
        )

        assert result is not None
        assert result.course == 3
        assert result.group_number == "CS-301"
        assert result.is_head_student is True

    @pytest.mark.asyncio
    async def test_update_profile_not_found(self, test_session):
        """Test update_profile returns None when user not found."""
        repo = UserRepository(test_session)
        result = await repo.update_profile(
            external_id=999999999,
            course=1
        )

        assert result is None


# =============================
# TicketRepository Tests
# =============================

class TestTicketRepository:
    """Tests for TicketRepository class."""

    @pytest.fixture
    async def test_user(self, test_session):
        """Create a test user."""
        user = User(
            external_id=555666,
            source=SourceType.TELEGRAM,
            full_name="Ticket Test User"
        )
        test_session.add(user)
        await test_session.commit()
        return user

    @pytest.fixture
    async def test_category(self, test_session):
        """Create a test category."""
        category = Category(name="Test Category")
        test_session.add(category)
        await test_session.commit()
        return category

    @pytest.mark.asyncio
    async def test_get_active_by_user_found(self, test_session, test_user, test_category):
        """Test get_active_by_user returns active ticket."""
        ticket = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.NEW,
            daily_id=1,
            question_text="Test question"
        )
        test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_active_by_user(555666, SourceType.TELEGRAM)

        assert result is not None
        assert result.id == ticket.id
        assert result.status == TicketStatus.NEW

    @pytest.mark.asyncio
    async def test_get_active_by_user_in_progress(self, test_session, test_user, test_category):
        """Test get_active_by_user returns IN_PROGRESS ticket."""
        ticket = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.IN_PROGRESS,
            daily_id=1,
            question_text="In progress question"
        )
        test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_active_by_user(555666, SourceType.TELEGRAM)

        assert result is not None
        assert result.status == TicketStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_get_active_by_user_closed(self, test_session, test_user, test_category):
        """Test get_active_by_user returns None for closed ticket."""
        ticket = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=1,
            question_text="Closed question"
        )
        test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_active_by_user(555666, SourceType.TELEGRAM)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_by_user_not_found(self, test_session):
        """Test get_active_by_user returns None when no user."""
        repo = TicketRepository(test_session)
        result = await repo.get_active_by_user(999999999, SourceType.TELEGRAM)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_admin_message_id_found(self, test_session, test_user, test_category):
        """Test get_by_admin_message_id returns ticket."""
        ticket = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.NEW,
            daily_id=1,
            question_text="Admin message test",
            admin_message_id=12345
        )
        test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_by_admin_message_id(12345)

        assert result is not None
        assert result.id == ticket.id
        assert result.admin_message_id == 12345

    @pytest.mark.asyncio
    async def test_get_by_admin_message_id_not_found(self, test_session):
        """Test get_by_admin_message_id returns None when not found."""
        repo = TicketRepository(test_session)
        result = await repo.get_by_admin_message_id(99999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history(self, test_session, test_user, test_category):
        """Test get_history returns user's tickets."""
        # Create multiple tickets
        for i in range(5):
            ticket = Ticket(
                user_id=test_user.id,
                category_id=test_category.id,
                source=SourceType.TELEGRAM,
                status=TicketStatus.CLOSED,
                daily_id=i + 1,
                question_text=f"Question {i + 1}"
            )
            test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_history(test_user.id, limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_history_empty(self, test_session, test_user):
        """Test get_history returns empty list when no tickets."""
        repo = TicketRepository(test_session)
        result = await repo.get_history(test_user.id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_closed_summaries_since(self, test_session, test_user, test_category):
        """Test get_closed_summaries_since returns summaries."""
        # Create closed tickets with summaries
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

        ticket1 = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=1,
            question_text="Q1",
            summary="Summary 1",
            closed_at=yesterday
        )
        ticket2 = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=2,
            question_text="Q2",
            summary="Summary 2",
            closed_at=yesterday
        )
        test_session.add_all([ticket1, ticket2])
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_closed_summaries_since(week_ago)

        assert len(result) == 2
        assert "Summary 1" in result
        assert "Summary 2" in result

    @pytest.mark.asyncio
    async def test_get_closed_summaries_since_excludes_none(self, test_session, test_user, test_category):
        """Test get_closed_summaries_since excludes tickets without summary."""
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

        ticket = Ticket(
            user_id=test_user.id,
            category_id=test_category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.CLOSED,
            daily_id=1,
            question_text="Q1",
            summary=None,  # No summary
            closed_at=yesterday
        )
        test_session.add(ticket)
        await test_session.commit()

        repo = TicketRepository(test_session)
        result = await repo.get_closed_summaries_since(week_ago)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_next_daily_id_first_of_day(self, test_session):
        """Test get_next_daily_id returns 1 for first ticket of day."""
        repo = TicketRepository(test_session)
        result = await repo.get_next_daily_id()

        assert result == 1

    @pytest.mark.asyncio
    async def test_get_next_daily_id_increments(self, test_session):
        """Test get_next_daily_id increments counter."""
        repo = TicketRepository(test_session)

        # Get three IDs
        id1 = await repo.get_next_daily_id()
        id2 = await repo.get_next_daily_id()
        id3 = await repo.get_next_daily_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3
