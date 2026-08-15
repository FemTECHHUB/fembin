"""Shared fixtures.

- `busy_client` / `busy_settings` — a live mock BUSY server, usable either as a ready
  BusyClient or as Settings for code (like app.domain.catalog.scheduler.run_catalog_sync)
  that builds its own client from settings.
- `woo_server` / `woo_client` — a live mock WooCommerce server, as the raw server (to
  inspect what was created) or as a ready WooCommerceClient (same underlying server).
- `catalog_sync_settings` — both mock servers at once, as Settings, for code that builds
  both clients from one Settings object (app.domain.catalog.scheduler.run_catalog_sync).
- `db_session` — a session against the real local dev MySQL (docker-compose, see README);
  there's no mocking the DB layer, only BUSY/WooCommerce. Each test gets a clean slate on
  the catalog tables and cleans up after itself.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.db.models import Category, MaterialCenter, Product, SyncState, WooSyncState
from app.db.session import SessionLocal
from app.integrations.woocommerce import WooCommerceClient
from tests.fixtures.mock_busy import run_mock_busy_server
from tests.fixtures.mock_busy import server_host_port as busy_server_host_port
from tests.fixtures.mock_woo import MockWooServer, run_mock_woo_server
from tests.fixtures.mock_woo import server_host_port as woo_server_host_port


@pytest_asyncio.fixture
async def busy_client() -> AsyncIterator[BusyClient]:
    with run_mock_busy_server() as server:
        host, port = busy_server_host_port(server)
        async with BusyClient(
            host=host, port=port, username="test-user", password="test-pwd"
        ) as client:
            yield client


@pytest.fixture
def busy_settings() -> Iterator[Settings]:
    with run_mock_busy_server() as server:
        host, port = busy_server_host_port(server)
        yield Settings(
            busy_host=host, busy_port=port, busy_username="test-user", busy_password="test-pwd"
        )


@pytest.fixture
def woo_server() -> Iterator[MockWooServer]:
    with run_mock_woo_server() as server:
        yield server


@pytest_asyncio.fixture
async def woo_client(woo_server: MockWooServer) -> AsyncIterator[WooCommerceClient]:
    host, port = woo_server_host_port(woo_server)
    async with WooCommerceClient(
        site_url=f"http://{host}:{port}",
        consumer_key="test-key",
        consumer_secret="test-secret",
    ) as client:
        yield client


@pytest.fixture
def catalog_sync_settings() -> Iterator[Settings]:
    with run_mock_busy_server() as busy_server, run_mock_woo_server() as woo_server:
        busy_host, busy_port = busy_server_host_port(busy_server)
        woo_host, woo_port = woo_server_host_port(woo_server)
        yield Settings(
            busy_host=busy_host,
            busy_port=busy_port,
            busy_username="test-user",
            busy_password="test-pwd",
            woo_site_url=f"http://{woo_host}:{woo_port}",
            woo_consumer_key="test-key",
            woo_consumer_secret="test-secret",
        )


def _clean_catalog_tables(session: Session) -> None:
    session.query(Product).delete()
    session.query(Category).delete()
    session.query(MaterialCenter).delete()
    session.query(SyncState).delete()
    session.query(WooSyncState).delete()
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
