from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TG_BOT_TOKEN: str
    VK_TOKEN: str
    TG_ADMIN_ID: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
