"""Tests for PostgreSQL database support."""
import pytest
from unittest.mock import patch
import os


class TestDatabaseURLConfig:
    """Tests for database URL configuration in Settings."""
    
    def test_default_sqlite_url(self):
        """Test that default database URL is SQLite."""
        # Clear DATABASE_URL to ensure SQLite default
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            # Reimport to get fresh settings
            from core.config import Settings
            settings = Settings(
                TG_BOT_TOKEN="test",
                TG_ADMIN_ID=123,
                TG_STAFF_CHAT_ID=-100123,
                DATABASE_URL=None
            )
            
            url = settings.get_database_url()
            assert "sqlite+aiosqlite" in url
    
    def test_postgresql_url_conversion(self):
        """Test that postgresql:// is converted to postgresql+asyncpg://."""
        from core.config import Settings
        
        settings = Settings(
            TG_BOT_TOKEN="test",
            TG_ADMIN_ID=123,
            TG_STAFF_CHAT_ID=-100123,
            DATABASE_URL="postgresql://user:pass@localhost:5432/db"
        )
        
        url = settings.get_database_url()
        assert url == "postgresql+asyncpg://user:pass@localhost:5432/db"
    
    def test_postgres_url_conversion(self):
        """Test that postgres:// (Heroku style) is converted properly."""
        from core.config import Settings
        
        settings = Settings(
            TG_BOT_TOKEN="test",
            TG_ADMIN_ID=123,
            TG_STAFF_CHAT_ID=-100123,
            DATABASE_URL="postgres://user:pass@localhost:5432/db"
        )
        
        url = settings.get_database_url()
        assert url == "postgresql+asyncpg://user:pass@localhost:5432/db"
    
    def test_asyncpg_url_unchanged(self):
        """Test that postgresql+asyncpg:// URL is not modified."""
        from core.config import Settings
        
        settings = Settings(
            TG_BOT_TOKEN="test",
            TG_ADMIN_ID=123,
            TG_STAFF_CHAT_ID=-100123,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        
        url = settings.get_database_url()
        assert url == "postgresql+asyncpg://user:pass@localhost:5432/db"


class TestDatabaseSetup:
    """Tests for database setup module."""
    
    def test_get_database_url_function(self):
        """Test get_database_url helper function."""
        from database.setup import get_database_url
        
        url = get_database_url()
        assert url is not None
        assert len(url) > 0
    
    def test_is_postgresql_function_with_sqlite(self):
        """Test is_postgresql returns False for SQLite."""
        # By default in tests, we use SQLite
        from database.setup import is_postgresql, DATABASE_URL
        
        # Check if actually using SQLite in test environment
        if "sqlite" in DATABASE_URL.lower():
            assert is_postgresql() is False
    
    def test_engine_creation(self):
        """Test that engine is created successfully."""
        from database.setup import engine
        
        assert engine is not None


class TestWebAppConfig:
    """Tests for Mini App configuration."""
    
    def test_webapp_defaults(self):
        """Test default webapp settings."""
        from core.config import Settings
        
        settings = Settings(
            TG_BOT_TOKEN="test",
            TG_ADMIN_ID=123,
            TG_STAFF_CHAT_ID=-100123
        )
        
        assert settings.WEBAPP_HOST == "0.0.0.0"
        assert settings.WEBAPP_PORT == 8080
        assert settings.WEBAPP_URL is None
    
    def test_webapp_custom_settings(self):
        """Test custom webapp settings."""
        from core.config import Settings
        
        settings = Settings(
            TG_BOT_TOKEN="test",
            TG_ADMIN_ID=123,
            TG_STAFF_CHAT_ID=-100123,
            WEBAPP_HOST="127.0.0.1",
            WEBAPP_PORT=3000,
            WEBAPP_URL="https://example.com"
        )
        
        assert settings.WEBAPP_HOST == "127.0.0.1"
        assert settings.WEBAPP_PORT == 3000
        assert settings.WEBAPP_URL == "https://example.com"
