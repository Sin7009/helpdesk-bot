"""Tests for Admin Panel in WebApp."""
import pytest
from unittest.mock import patch
from aiohttp import web
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from webapp.server import create_app
from database.models import Base, User, Ticket, TicketStatus, UserRole, SourceType, Category

# --- Fixtures ---

@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    yield async_session

    await engine.dispose()

@pytest.fixture
async def client(aiohttp_client, test_db):
    """
    Create a test client with patched database session.
    We patch 'webapp.server.new_session' to return our in-memory session.
    """
    app = create_app()

    # Helper to create a context manager that yields a session
    class MockSessionCtx:
        def __init__(self, session_factory):
            self.factory = session_factory

        async def __aenter__(self):
            self.session = self.factory()
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self.session.close()

    # Patch the session usage in webapp.server
    with patch("webapp.server.new_session", return_value=MockSessionCtx(test_db)):
        yield await aiohttp_client(app)

# --- Tests ---

@pytest.mark.asyncio
async def test_admin_dashboard_html(client):
    """Test that admin dashboard returns HTML."""
    resp = await client.get("/webapp/admin")
    assert resp.status == 200
    text = await resp.text()
    assert "Админ-панель" in text
    # ИСПРАВЛЕНО: проверяем актуальное имя функции инициализации
    assert "init()" in text

@pytest.mark.asyncio
async def test_api_admin_data_unauthorized(client):
    """Test access denied without user_id."""
    resp = await client.get("/api/admin/data")
    assert resp.status == 401
    data = await resp.json()
    assert "Auth required" in data["error"]

@pytest.mark.asyncio
async def test_api_admin_data_forbidden_for_user(client, test_db):
    """Test access denied for regular user."""
    # 1. Create regular user
    async with test_db() as session:
        user = User(
            external_id=12345,
            source=SourceType.TELEGRAM,
            role=UserRole.USER  # Regular user
        )
        session.add(user)
        await session.commit()

    # 2. Try to access
    resp = await client.get("/api/admin/data?user_id=12345")
    assert resp.status == 403
    data = await resp.json()
    assert "Access denied" in data["error"]

@pytest.mark.asyncio
async def test_api_admin_data_success(client, test_db):
    """Test successful data retrieval for admin."""
    # 1. Prepare data
    async with test_db() as session:
        # Admin User
        admin = User(
            external_id=999,
            source=SourceType.TELEGRAM,
            username="admin",
            role=UserRole.ADMIN
        )
        # Category
        cat = Category(name="IT Support")
        session.add_all([admin, cat])
        await session.flush()

        # Tickets
        t1 = Ticket(
            daily_id=1,
            user_id=admin.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.NEW,
            question_text="Problem 1",
            category_id=cat.id
        )
        t2 = Ticket(
            daily_id=2,
            user_id=admin.id,
            source=SourceType.TELEGRAM,
            status=TicketStatus.IN_PROGRESS,
            question_text="Problem 2"
        )
        session.add_all([t1, t2])
        await session.commit()

    # 2. Call API
    resp = await client.get("/api/admin/data?user_id=999")
    assert resp.status == 200

    data = await resp.json()

    # 3. Verify Stats
    stats = data["stats"]
    assert stats["new"] == 1
    assert stats["in_progress"] == 1
    assert stats["closed"] == 0

    # 4. Verify Ticket List
    tickets = data["tickets"]
    assert len(tickets) == 2
    assert tickets[0]["daily_id"] == 2  # Order by desc created_at
    assert tickets[0]["status"] == "in_progress"
    assert tickets[1]["status"] == "new"
    assert tickets[1]["category"] == "IT Support"
