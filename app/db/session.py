"""SQLAlchemy engine and session factory, built from app.config settings."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    # Defaults (pool_size=5, max_overflow=10, no recycle) are fine for local dev but
    # too small for production concurrency, and without pool_recycle a connection idle
    # longer than the DB server's own timeout surfaces as "MySQL server has gone away"
    # instead of being quietly replaced. 1 hour is comfortably under a typical 8h
    # wait_timeout; tune pool_size/max_overflow to real traffic once measured.
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a request-scoped session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
