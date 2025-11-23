from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Имена переменных должны точно совпадать с тем, что в .env (капсом)
    TG_BOT_TOKEN: str
    TG_ADMIN_ID: int
    
    # Добавляем базу данных с дефолтным значением
    DB_NAME: str = "/app/data/support.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Это заставит бота игнорировать лишние строки в .env
    )

settings = Settings()
