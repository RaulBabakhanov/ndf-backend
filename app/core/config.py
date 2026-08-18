from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_running_in_container() -> bool:
    return Path("/.dockerenv").exists()


def default_database_url() -> str:
    if is_running_in_container():
        return "postgresql+asyncpg://ndf_user:ndf_password@database:5432/ndf-database"
    return "postgresql+asyncpg://ndf_user:ndf_password@localhost:5433/ndf-database"


class Settings(BaseSettings):
    app_name: str = "NDF Bayi Portal API"
    environment: str = "development"
    database_url: str = Field(default_factory=default_database_url)
    jwt_secret: str = "development-only-change-me"
    admin_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_expected_hostname: str = ""
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
