from pathlib import Path
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
    
    # OpenRouter API key for LLM-based ticket summarization
    OPENROUTER_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Это заставит бота игнорировать лишние строки в .env
    )

settings = Settings()
