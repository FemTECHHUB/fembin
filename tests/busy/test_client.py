"""Integration tests for BusyClient against the mock BUSY server (tests/fixtures/mock_busy.py)."""

import pytest

from app.busy.client import BusyClient, BusyError
from app.busy.xml_util import parse_element_xml, parse_rowset_xml
from tests.fixtures.mock_busy import run_mock_busy_server, server_host_port


async def test_run_query_returns_parseable_rowset_xml(busy_client: BusyClient) -> None:
    xml = await busy_client.run_query("SELECT Code, Name FROM Master1 WHERE MasterType = 6")
    rows = parse_rowset_xml(xml)
    codes = {r["Code"] for r in rows}
    assert {"101", "102", "103"}.issubset(codes)


async def test_run_query_surfaces_bit_columns_as_text(busy_client: BusyClient) -> None:
    xml = await busy_client.run_query(
        "SELECT Code, BlockedMaster FROM Master1 WHERE MasterType = 6"
    )
    rows = parse_rowset_xml(xml)
    blocked = {r["Code"]: r["BlockedMaster"] for r in rows}
    assert blocked["103"] == "True"
    assert blocked["101"] == "False"


async def test_get_master_xml_returns_parseable_element_xml(busy_client: BusyClient) -> None:
    xml = await busy_client.get_master_xml(101)
    result = parse_element_xml(xml)
    assert isinstance(result, dict)
    item = result["Item"]
    assert isinstance(item, dict)
    assert item["Name"] == "Fake Item 101"


async def test_get_voucher_xml_returns_parseable_element_xml(busy_client: BusyClient) -> None:
    xml = await busy_client.get_voucher_xml(9701)
    result = parse_element_xml(xml)
    assert isinstance(result, dict)
    sale = result["Sale"]
    assert isinstance(sale, dict)
    assert sale["VchCode"] == "9701"


async def test_call_without_credentials_raises_busy_error() -> None:
    with run_mock_busy_server() as server:
        host, port = server_host_port(server)
        async with BusyClient(host=host, port=port, username="", password="") as client:
            with pytest.raises(BusyError, match="Missing UserName/Pwd"):
                await client.run_query("SELECT 1")
