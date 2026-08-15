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

    # Catalog sync (Sprint 1) — mirrors the prototype's config.sync.intervalMinutes.
    # Disabled by default: if the API is ever scaled to multiple worker processes, only
    # one of them should run the periodic scheduler, so this is opt-in per-process rather
    # than always-on. The manual POST /api/v1/sync/products trigger works regardless.
    catalog_sync_enabled: bool = False
    catalog_sync_interval_seconds: float = 300.0

    # WooCommerce REST API (Sprint 2) — dedicated Read/Write key, not an admin's (PRD §6).
    # Left blank, the woo-push step is skipped entirely rather than failing the whole sync.
    woo_site_url: str = ""
    woo_consumer_key: str = ""
    woo_consumer_secret: str = ""
    woo_new_product_status: str = "private"

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — env is read once per process."""
    return Settings()
