"""Shared fixtures.

- `busy_client` / `busy_settings` — a live mock BUSY server, usable either as a ready
  BusyClient or as Settings for code (like app.domain.catalog.scheduler.run_catalog_sync)
  that builds its own client from settings.
- `db_session` — a session against the real local dev MySQL (docker-compose, see README);
  there's no mocking the DB layer, only BUSY. Each test gets a clean slate on the catalog
  tables and cleans up after itself.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.db.models import Category, MaterialCenter, Product, SyncState
from app.db.session import SessionLocal
from tests.fixtures.mock_busy import run_mock_busy_server, server_host_port


@pytest_asyncio.fixture
async def busy_client() -> AsyncIterator[BusyClient]:
    with run_mock_busy_server() as server:
        host, port = server_host_port(server)
        async with BusyClient(
            host=host, port=port, username="test-user", password="test-pwd"
        ) as client:
            yield client


@pytest.fixture
def busy_settings() -> Iterator[Settings]:
    with run_mock_busy_server() as server:
        host, port = server_host_port(server)
        yield Settings(
            busy_host=host, busy_port=port, busy_username="test-user", busy_password="test-pwd"
        )


def _clean_catalog_tables(session: Session) -> None:
    session.query(Product).delete()
    session.query(Category).delete()
    session.query(MaterialCenter).delete()
    session.query(SyncState).delete()
    session.commit()


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    _clean_catalog_tables(session)
    try:
        yield session
    finally:
        session.rollback()
        _clean_catalog_tables(session)
        session.close()
