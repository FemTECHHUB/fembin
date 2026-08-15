"""Shared fixtures for BUSY-facing tests: a live mock BUSY server per test module."""

from collections.abc import AsyncIterator

import pytest_asyncio

from app.busy.client import BusyClient
from tests.fixtures.mock_busy import run_mock_busy_server, server_host_port


@pytest_asyncio.fixture
async def busy_client() -> AsyncIterator[BusyClient]:
    with run_mock_busy_server() as server:
        host, port = server_host_port(server)
        async with BusyClient(
            host=host, port=port, username="test-user", password="test-pwd"
        ) as client:
            yield client
