"""Extended tests for middlewares to improve coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Update
from middlewares.db import DbSessionMiddleware


class TestDbSessionMiddleware:
    """Tests for DbSessionMiddleware."""

    @pytest.fixture
    def mock_session_pool(self):
        """Create a mock session pool."""
        pool = MagicMock()
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        pool.return_value = mock_context
        return pool

    @pytest.mark.asyncio
    async def test_middleware_injects_session(self, mock_session_pool):
        """Test middleware injects session into data."""
        middleware = DbSessionMiddleware(mock_session_pool)

        handler = AsyncMock()
        handler.return_value = "result"

        event = MagicMock(spec=Message)
        data = {}

        result = await middleware(handler, event, data)

        assert result == "result"
        assert "session" in data
        handler.assert_called_once_with(event, data)

    @pytest.mark.asyncio
    async def test_middleware_handles_exception(self, mock_session_pool):
        """Test middleware re-raises exceptions from handler."""
        middleware = DbSessionMiddleware(mock_session_pool)

        handler = AsyncMock()
        handler.side_effect = ValueError("Test error")

        event = MagicMock(spec=Message)
        data = {}

        with pytest.raises(ValueError) as exc_info:
            await middleware(handler, event, data)

        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_middleware_closes_session(self, mock_session_pool):
        """Test middleware properly closes session after use."""
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_session_pool.return_value = mock_context

        middleware = DbSessionMiddleware(mock_session_pool)

        handler = AsyncMock()
        event = MagicMock(spec=Message)
        data = {}

        await middleware(handler, event, data)

        # Context manager should have been used
        mock_context.__aenter__.assert_called_once()
        mock_context.__aexit__.assert_called_once()
