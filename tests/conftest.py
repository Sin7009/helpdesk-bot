import os
import pytest
from unittest.mock import MagicMock

# 1. Set environment variables BEFORE importing application code
os.environ["TG_BOT_TOKEN"] = "mock_token"
os.environ["TG_ADMIN_ID"] = "12345"
os.environ["TG_STAFF_CHAT_ID"] = "999"

@pytest.fixture(autouse=True)
def mock_settings():
    """
    Ensures settings are loaded with mock values.
    This fixture runs automatically for all tests.
    """
    pass
