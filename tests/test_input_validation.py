"""Test input validation and error handling."""
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from services.ticket_service import create_ticket

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_session():
    """Create a test database session."""
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
async def test_create_ticket_empty_text(test_session):
    """Test that creating a ticket with empty text raises ValueError."""
    bot = AsyncMock()
    
    with pytest.raises(ValueError, match="Question text cannot be empty"):
        await create_ticket(
            test_session,
            user_id=123,
            source="tg",
            text="",
            bot=bot,
            category_name="General",
            user_full_name="Test User"
        )


@pytest.mark.asyncio
async def test_create_ticket_whitespace_only(test_session):
    """Test that creating a ticket with whitespace-only text raises ValueError."""
    bot = AsyncMock()
    
    with pytest.raises(ValueError, match="Question text cannot be empty"):
        await create_ticket(
            test_session,
            user_id=123,
            source="tg",
            text="   \n\t  ",
            bot=bot,
            category_name="General",
            user_full_name="Test User"
        )


@pytest.mark.asyncio
async def test_create_ticket_too_long(test_session):
    """Test that creating a ticket with too long text raises ValueError."""
    bot = AsyncMock()
    
    # Create a text longer than 10000 characters
    long_text = "x" * 10001
    
    with pytest.raises(ValueError, match="Question text is too long"):
        await create_ticket(
            test_session,
            user_id=123,
            source="tg",
            text=long_text,
            bot=bot,
            category_name="General",
            user_full_name="Test User"
        )


@pytest.mark.asyncio
async def test_create_ticket_strips_whitespace(test_session):
    """Test that ticket text is properly stripped of leading/trailing whitespace."""
    bot = AsyncMock()
    
    ticket = await create_ticket(
        test_session,
        user_id=123,
        source="tg",
        text="  Hello World  \n\t",
        bot=bot,
        category_name="General",
        user_full_name="Test User"
    )
    
    assert ticket.question_text == "Hello World"


@pytest.mark.asyncio
async def test_create_ticket_valid_at_max_length(test_session):
    """Test that creating a ticket at exactly max length works."""
    bot = AsyncMock()
    
    # Create a text exactly 10000 characters
    max_length_text = "x" * 10000
    
    ticket = await create_ticket(
        test_session,
        user_id=123,
        source="tg",
        text=max_length_text,
        bot=bot,
        category_name="General",
        user_full_name="Test User"
    )
    
    assert len(ticket.question_text) == 10000
