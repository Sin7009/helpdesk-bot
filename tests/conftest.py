"""
Pytest configuration and fixtures for the test suite.

This module loads test environment variables from .env.test before any test
modules are imported, ensuring that Settings validation succeeds.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import pytest
from unittest.mock import AsyncMock, MagicMock

# Load test environment variables BEFORE any imports from the project
# This ensures that when core.config.Settings() is instantiated,
# it finds the required environment variables
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
TEST_ENV_FILE = PROJECT_ROOT / ".env.test"

if TEST_ENV_FILE.exists():
    load_dotenv(TEST_ENV_FILE, override=True)
else:
    # Fallback: set minimal required variables if .env.test doesn't exist
    os.environ.setdefault("TG_BOT_TOKEN", "test_token_12345")
    os.environ.setdefault("TG_ADMIN_ID", "123456789")
    os.environ.setdefault("TG_STAFF_CHAT_ID", "-100123456789")
    os.environ.setdefault("DB_NAME", ":memory:")


@pytest.fixture
def mock_bot():
    """
    Create a properly configured bot mock for testing.
    
    This fixture ensures that bot.send_message() returns a message object
    with a real integer message_id, preventing SQLite binding errors when
    the code tries to save the message_id to the database.
    """
    bot = AsyncMock()
    
    # Configure send_message to return a message with an integer message_id
    mock_message = MagicMock()
    mock_message.message_id = 12345  # Use a real integer, not an AsyncMock
    bot.send_message.return_value = mock_message
    
    return bot
