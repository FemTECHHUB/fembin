"""Pagination test — Sprint 1 DoD: "Pagination verified against a query returning more
rows than one page size, in a test." Runs against the mock BUSY server's paginatable
dataset (tests/fixtures/mock_busy.py), which deliberately has more rows sharing one Stamp
value than fit on a page, to prove the (Stamp, Code) keyset cursor doesn't skip or loop
forever on ties — a real risk given how coarse BUSY's actual Stamp values are (CLAUDE.md §8).
"""

from collections.abc import Callable, Coroutine
from typing import Any

from app.busy.client import BusyClient
from app.busy.pagination import fetch_all_pages


async def test_fetch_all_pages_paginates_across_stamp_ties(busy_client: BusyClient) -> None:
    call_count = 0
    original_run_query: Callable[[str], Coroutine[Any, Any, str]] = busy_client.run_query

    async def counting_run_query(sql: str) -> str:
        nonlocal call_count
        call_count += 1
        return await original_run_query(sql)

    busy_client.run_query = counting_run_query  # type: ignore[method-assign]

    rows = await fetch_all_pages(
        busy_client,
        select_columns=["Code", "Name", "Stamp", "BlockedMaster", "DeactiveMaster"],
        from_and_where="Master1 WHERE MasterType = 6",
        since=-1,
        page_size=3,
    )

    codes = [int(r["Code"]) for r in rows]
    assert codes == [301, 302, 303, 304, 305, 306, 307, 308]
    assert call_count == 3, "8 rows at page_size=3 with a 4-way Stamp tie must take 3 pages"


async def test_fetch_all_pages_incremental_since_excludes_already_seen(
    busy_client: BusyClient,
) -> None:
    rows = await fetch_all_pages(
        busy_client,
        select_columns=["Code", "Name", "Stamp", "BlockedMaster", "DeactiveMaster"],
        from_and_where="Master1 WHERE MasterType = 6",
        since=20,
        page_size=3,
    )
    codes = {int(r["Code"]) for r in rows}
    assert codes == {307, 308}
