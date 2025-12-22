"""Extended tests for scheduler service to improve coverage."""
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, Ticket, Category, User, TicketStatus, SourceType, TicketPriority
from services.scheduler import send_daily_statistics, send_weekly_faq_analysis, setup_scheduler

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


class TestDailyStatisticsExtended:
    """Extended tests for send_daily_statistics."""

    @pytest.mark.asyncio
    async def test_statistics_with_ratings(self, test_session):
        """Test statistics includes average rating."""
        # Create test data with ratings
        user = User(external_id=123, source=SourceType.TELEGRAM, full_name="Test User")
        test_session.add(user)
        await test_session.commit()

        category = Category(name="IT")
        test_session.add(category)
        await test_session.commit()

        today = datetime.datetime.now()
        # Create tickets with ratings
        for i in range(3):
            ticket = Ticket(
                user_id=user.id,
                category_id=category.id,
                source=SourceType.TELEGRAM,
                status=TicketStatus.CLOSED,
                daily_id=i + 1,
                question_text=f"Question {i}",
                created_at=today,
                closed_at=today,
                rating=4 + (i % 2)  # Ratings of 4, 5, 4
            )
            test_session.add(ticket)
        await test_session.commit()

        bot = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = test_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch('services.scheduler.new_session', return_value=mock_session_ctx):
            await send_daily_statistics(bot)

        assert bot.send_message.called
        args, kwargs = bot.send_message.call_args
        message_text = args[1]

        # Should include rating info
        assert "Средняя оценка" in message_text
        # Average of 4+5+4 = 4.33
        assert "/5" in message_text

    @pytest.mark.asyncio
    async def test_statistics_with_priorities(self, test_session):
        """Test statistics includes priority distribution."""
        user = User(external_id=456, source=SourceType.TELEGRAM, full_name="Test User")
        test_session.add(user)
        await test_session.commit()

        category = Category(name="Support")
        test_session.add(category)
        await test_session.commit()

        today = datetime.datetime.now()
        # Create tickets with different priorities
        priorities = [
            TicketPriority.URGENT,
            TicketPriority.HIGH,
            TicketPriority.NORMAL,
            TicketPriority.NORMAL,
            TicketPriority.LOW
        ]
        for i, priority in enumerate(priorities):
            ticket = Ticket(
                user_id=user.id,
                category_id=category.id,
                source=SourceType.TELEGRAM,
                status=TicketStatus.NEW,
                daily_id=i + 1,
                question_text=f"Question {i}",
                created_at=today,
                priority=priority
            )
            test_session.add(ticket)
        await test_session.commit()

        bot = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = test_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch('services.scheduler.new_session', return_value=mock_session_ctx):
            await send_daily_statistics(bot)

        assert bot.send_message.called
        args, kwargs = bot.send_message.call_args
        message_text = args[1]

        assert "приоритетам" in message_text

    @pytest.mark.asyncio
    async def test_statistics_with_response_time(self, test_session):
        """Test statistics includes average response time."""
        user = User(external_id=789, source=SourceType.TELEGRAM, full_name="Test User")
        test_session.add(user)
        await test_session.commit()

        category = Category(name="General")
        test_session.add(category)
        await test_session.commit()

        today = datetime.datetime.now()
        # Create a ticket with first_response_at set
        ticket = Ticket(
            user_id=user.id,
            category_id=category.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.IN_PROGRESS,
            daily_id=1,
            question_text="Question with response",
            created_at=today - datetime.timedelta(hours=1),
            first_response_at=today
        )
        test_session.add(ticket)
        await test_session.commit()

        bot = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = test_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch('services.scheduler.new_session', return_value=mock_session_ctx):
            await send_daily_statistics(bot)

        assert bot.send_message.called
        args, kwargs = bot.send_message.call_args
        message_text = args[1]

        assert "Среднее время ответа" in message_text


class TestWeeklyFAQAnalysis:
    """Tests for weekly FAQ analysis."""

    @pytest.mark.asyncio
    async def test_weekly_faq_analysis_few_tickets(self):
        """Test weekly analysis skips when too few tickets."""
        bot = AsyncMock()

        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        # Mock repo to return few summaries (less than 5)
        with patch('services.scheduler.new_session', return_value=mock_session_ctx), \
             patch('services.scheduler.TicketRepository') as MockTicketRepo:

            mock_repo = AsyncMock()
            mock_repo.get_closed_summaries_since.return_value = ["Sum1", "Sum2"]  # Only 2
            MockTicketRepo.return_value = mock_repo

            await send_weekly_faq_analysis(bot)

            # Should not send message when too few tickets
            bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_weekly_faq_analysis_success(self):
        """Test weekly analysis sends report when enough tickets."""
        bot = AsyncMock()

        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        # Mock repo to return enough summaries
        summaries = [f"Summary {i}" for i in range(10)]

        with patch('services.scheduler.new_session', return_value=mock_session_ctx), \
             patch('services.scheduler.TicketRepository') as MockTicketRepo, \
             patch('services.scheduler.LLMService') as MockLLMService:

            mock_repo = AsyncMock()
            mock_repo.get_closed_summaries_since.return_value = summaries
            MockTicketRepo.return_value = mock_repo

            MockLLMService.suggest_faq_updates = AsyncMock(
                return_value="Suggested FAQ: How to reset password?\n/add_faq пароль Инструкция..."
            )

            await send_weekly_faq_analysis(bot)

            # Should send analysis message
            bot.send_message.assert_called_once()
            args, kwargs = bot.send_message.call_args
            message_text = args[1]
            assert "AI-анализ" in message_text
            assert "10" in message_text  # Number of analyzed tickets

    @pytest.mark.asyncio
    async def test_weekly_faq_analysis_error_handling(self):
        """Test weekly analysis handles errors gracefully."""
        bot = AsyncMock()

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.side_effect = Exception("Database error")
        mock_session_ctx.__aexit__.return_value = AsyncMock()

        with patch('services.scheduler.new_session', return_value=mock_session_ctx):
            # Should not raise exception
            await send_weekly_faq_analysis(bot)

            # No message should be sent on error
            bot.send_message.assert_not_called()


class TestSchedulerSetup:
    """Tests for scheduler setup."""

    def test_setup_scheduler(self):
        """Test scheduler is configured correctly."""
        bot = AsyncMock()

        with patch('services.scheduler.AsyncIOScheduler') as MockScheduler:
            mock_scheduler = MagicMock()
            MockScheduler.return_value = mock_scheduler

            result = setup_scheduler(bot)

            # Verify jobs are added
            assert mock_scheduler.add_job.call_count == 2
            mock_scheduler.start.assert_called_once()

            # Check job configurations
            calls = mock_scheduler.add_job.call_args_list

            # First call: daily statistics
            first_call = calls[0]
            assert first_call[0][0] == send_daily_statistics
            assert first_call[0][1] == 'cron'
            assert first_call[1]['hour'] == 23
            assert first_call[1]['minute'] == 59

            # Second call: weekly analysis
            second_call = calls[1]
            assert second_call[0][0] == send_weekly_faq_analysis
            assert second_call[0][1] == 'cron'
            assert second_call[1]['day_of_week'] == 'sun'
