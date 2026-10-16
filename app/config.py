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
    # Products sync strategy (CLAUDE.md §8 — verified 2026-09-04): BUSY's Stamp does NOT
    # advance when an item is edited, so a Stamp-incremental products sync silently misses
    # name/price changes; only a full `Master1` re-pull sees them. Three modes:
    #   "stamp"    — Stamp-incremental only, never auto-full. Cheapest, but MISSES edits
    #                (the bug above). Use only if you know a specific BUSY install bumps
    #                Stamp on edits, or you run periodic full syncs some other way.
    #   "full"     — full `Master1` re-pull every run (+ per-item GetMasterXML detail).
    #                Correct, and trivial on a tiny catalog; heavy on a large install.
    #   "reconcile" — Stamp-incremental normally, but a FULL re-pull at least every
    #                `catalog_sync_products_reconcile_interval_seconds`. Balances load and
    #                edit freshness for a bigger BUSY install. Since BUSY only reports a
    #                company-wide Stamp batch counter (not per-row versions), an edit can
    #                still appear one interval late.
    # Default is "reconcile", not "full" — confirmed live 2026-10-15 against a real
    # 14,314-item BUSY install: "full" made one sync pass take upwards of an hour, which
    # on a short interval meant a near-permanent full-catalog scan against BUSY and
    # repeated session drops. "full" is still fine for a tiny catalog (this repo's own
    # ~9-item test company uses it explicitly in tests/conftest.py), just don't rely on
    # the default for that anymore — pass it explicitly.
    catalog_sync_products_strategy: str = "reconcile"
    catalog_sync_products_reconcile_interval_seconds: float = 3600.0
    # How many items' GetMasterXML detail calls run concurrently during products sync —
    # confirmed live 2026-10-15 at a 14k-item install: fully sequential (the old
    # behavior) made one "full" pass take upwards of an hour. Keep modest — BUSY is one
    # instance with no proven concurrent-request resilience (CLAUDE.md §8).
    catalog_sync_products_detail_concurrency: int = 8

    # WooCommerce REST API (Sprint 2) — dedicated Read/Write key, not an admin's (PRD §6).
    # Left blank, the woo-push step is skipped entirely rather than failing the whole sync.
    woo_site_url: str = ""
    woo_consumer_key: str = ""
    woo_consumer_secret: str = ""
    woo_new_product_status: str = "private"

    # Outbox worker — every BUSY write goes through this queue (CLAUDE.md §2.2). Off by
    # default per-process, same multi-worker-process reasoning as catalog_sync_enabled.
    outbox_worker_enabled: bool = False
    outbox_worker_interval_seconds: float = 5.0

    # Auth (PRD NFR6 — every action tied to a real user/material center, not the shared
    # BUSY service account). Dev-only default secret; a real deployment MUST override this
    # via env (CLAUDE.md §6 — no secrets in code).
    jwt_secret_key: str = "dev-only-change-me-3f8a1c9d7b2e4f60a5d8c1b3e7f92046"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # one working shift

    # Logging
    log_level: str = "INFO"

    # FastAPI's interactive docs (/docs, /redoc, /openapi.json) hand anyone who finds
    # them a complete map of the API surface, auth-free. Dev-friendly default like
    # jwt_secret_key above — DEPLOYMENT.md's checklist requires this be set to false in
    # production, same enforcement mechanism as that secret.
    api_docs_enabled: bool = True

    # Per-IP request budget for POST /auth/login (slowapi) — unlimited password-guessing
    # attempts was a real gap found in a 2026-10-16 production-readiness audit.
    login_rate_limit: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — env is read once per process."""
    return Settings()
