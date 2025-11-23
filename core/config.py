from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Обязательные переменные (должны быть в .env или environment docker-compose)
    TG_BOT_TOKEN: str
    TG_ADMIN_ID: int
    
    # Опциональные (с дефолтом)
    DB_NAME: str = "support.db" 

    # Настройки: читать .env и ИГНОРИРОВАТЬ лишние переменные (extra="ignore")
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # <-- Это спасет от ошибки "Extra inputs are not permitted"
    )

settings = Settings()
