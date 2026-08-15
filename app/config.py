"""Environment-driven settings — the only place env vars are read in the app."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, populated from environment variables / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "mysql+pymysql://fembin:fembin@localhost:3307/fembin"

    # BUSY "as Web Service" connection
    busy_host: str = "127.0.0.1"
    busy_port: int = 981
    busy_username: str = ""
    busy_password: str = ""
    busy_timeout_seconds: float = 30.0

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — env is read once per process."""
    return Settings()
