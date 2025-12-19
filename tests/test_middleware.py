import pytest
from unittest.mock import AsyncMock, MagicMock
from middlewares.db import DbSessionMiddleware

@pytest.mark.asyncio
async def test_db_session_middleware():
    # Mock session pool
    mock_session = AsyncMock()
    mock_session_pool = MagicMock()
    # __aenter__ and __aexit__ are needed for async context manager
    mock_session_pool.return_value.__aenter__.return_value = mock_session
    mock_session_pool.return_value.__aexit__.return_value = None

    middleware = DbSessionMiddleware(mock_session_pool)

    # Mock handler
    async def mock_handler(event, data):
        assert "session" in data
        assert data["session"] == mock_session
        return "OK"

    data = {}
    event = MagicMock()

    result = await middleware(mock_handler, event, data)

    assert result == "OK"
    mock_session_pool.assert_called_once()
