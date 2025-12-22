from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for flexible path resolution
BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    # Имена переменных должны точно совпадать с тем, что в .env (капсом)
    TG_BOT_TOKEN: str
    TG_ADMIN_ID: int
    TG_STAFF_CHAT_ID: int

    # Добавляем базу данных с дефолтным значением
    # Используем относительный путь для локальной разработки
    # Docker volume override это значение через .env
    DB_NAME: str = str(BASE_DIR / "support.db")
    
    # PostgreSQL support: DATABASE_URL takes precedence over DB_NAME
    # Example: postgresql+asyncpg://user:password@localhost:5432/helpdesk
    DATABASE_URL: Optional[str] = None
    
    # OpenRouter API key for LLM-based ticket summarization
    OPENROUTER_API_KEY: str = ""
    
    # Model name for summarization (default per your request)
    LLM_MODEL_NAME: str = "google/gemini-3-flash-preview"
    
    # Working hours for support (24-hour format, UTC+3 Moscow time)
    SUPPORT_HOURS_START: int = 9   # 09:00
    SUPPORT_HOURS_END: int = 18    # 18:00
    SUPPORT_TIMEZONE: str = "Europe/Moscow"
    
    # Enable/disable working hours check (set to False to accept tickets 24/7)
    ENABLE_WORKING_HOURS: bool = True
    
    # Reminder settings for unprocessed tickets
    STALE_TICKET_HOURS: int = 4  # Hours before a ticket is considered stale
    REMINDER_INTERVAL_MINUTES: int = 60  # How often to check for stale tickets
    
    # Telegram Mini App settings
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080
    WEBAPP_URL: Optional[str] = None  # Public URL for Mini App, e.g., https://example.com/webapp

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Это заставит бота игнорировать лишние строки в .env
    )
    
    def get_database_url(self) -> str:
        """Get the database URL, preferring DATABASE_URL over DB_NAME.
        
        Returns:
            str: SQLAlchemy async database URL
        """
        if self.DATABASE_URL:
            # Handle postgres:// -> postgresql:// conversion for compatibility
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        # Default to SQLite
        return f"sqlite+aiosqlite:///{self.DB_NAME}"

settings = Settings()
