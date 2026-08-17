from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NDF Bayi Portal API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://ndf_user:ndf_password@localhost:5433/ndf-database"
    jwt_secret: str = "development-only-change-me"
    admin_key: str = ""
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
