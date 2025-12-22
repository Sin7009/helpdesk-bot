"""Tests for Telegram Mini App web server."""
import pytest
from aiohttp import web
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from webapp.server import create_app, api_tickets, api_ticket_detail
from database.models import Base, User, Ticket, Message, Category, SourceType, TicketStatus, SenderRole


class TestWebAppRoutes:
    """Test web app route configuration."""
    
    def test_create_app_returns_application(self):
        """Test that create_app returns a valid aiohttp Application."""
        app = create_app()
        assert isinstance(app, web.Application)
    
    def test_routes_are_registered(self):
        """Test that all expected routes are registered."""
        app = create_app()
        
        routes = [route.resource.canonical for route in app.router.routes()]
        
        assert '/' in routes
        assert '/health' in routes
        assert '/webapp/tickets' in routes
        assert '/api/tickets' in routes
        assert '/api/tickets/{ticket_id}' in routes


@pytest.fixture
async def webapp_test_engine():
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def webapp_test_session(webapp_test_engine):
    """Create a test database session."""
    async_session_factory = async_sessionmaker(
        webapp_test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health check endpoint."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/health')
        assert resp.status == 200
        
        data = await resp.json()
        assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_index_redirects():
    """Test that index redirects to tickets page."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/', allow_redirects=False)
        assert resp.status == 302
        assert resp.headers.get('Location') == '/webapp/tickets'


@pytest.mark.asyncio
async def test_student_tickets_page():
    """Test the student tickets HTML page."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/webapp/tickets')
        assert resp.status == 200
        
        text = await resp.text()
        assert 'Мои заявки' in text
        assert 'telegram-web-app.js' in text


@pytest.mark.asyncio
async def test_api_tickets_requires_user_id():
    """Test that API requires user_id parameter."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/api/tickets')
        assert resp.status == 400
        
        data = await resp.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_api_tickets_invalid_user_id():
    """Test API with invalid user_id."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/api/tickets?user_id=invalid')
        assert resp.status == 400
        
        data = await resp.json()
        assert "error" in data
        assert "number" in data["error"].lower()


@pytest.mark.asyncio
async def test_api_ticket_detail_requires_user_id():
    """Test that ticket detail API requires user_id."""
    app = create_app()
    
    from aiohttp.test_utils import TestClient, TestServer
    
    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/api/tickets/1')
        assert resp.status == 400
        
        data = await resp.json()
        assert "error" in data


class TestMiniAppButton:
    """Tests for Mini App button in telegram handler."""
    
    def test_menu_without_webapp_url(self):
        """Test menu keyboard without WEBAPP_URL configured."""
        from handlers.telegram import get_menu_kb
        from core.config import settings
        
        # Save original value
        original_url = settings.WEBAPP_URL
        
        try:
            # Temporarily set to None
            settings.WEBAPP_URL = None
            
            kb = get_menu_kb()
            
            # Check that web_app button is not present
            has_webapp_button = False
            for row in kb.inline_keyboard:
                for button in row:
                    if button.web_app is not None:
                        has_webapp_button = True
            
            assert not has_webapp_button
        finally:
            # Restore original value
            settings.WEBAPP_URL = original_url
    
    def test_menu_with_webapp_url(self):
        """Test menu keyboard with WEBAPP_URL configured."""
        from handlers.telegram import get_menu_kb
        from core.config import settings
        
        # Save original value
        original_url = settings.WEBAPP_URL
        
        try:
            # Temporarily set URL
            settings.WEBAPP_URL = "https://example.com"
            
            kb = get_menu_kb()
            
            # Check that web_app button is present
            has_webapp_button = False
            for row in kb.inline_keyboard:
                for button in row:
                    if button.web_app is not None:
                        has_webapp_button = True
                        assert "example.com" in button.web_app.url
            
            assert has_webapp_button
        finally:
            # Restore original value
            settings.WEBAPP_URL = original_url
