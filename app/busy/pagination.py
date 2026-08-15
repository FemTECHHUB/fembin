"""Keyset pagination for BUSY's SC=1 SQL queries — PRD §11's "paginate every bulk sync
query" requirement.

BUSY's `Stamp` column is a coarse changelog counter: real values observed were small
(1-4) even across thousands of records (CLAUDE.md §8), so many rows can share one Stamp
value. A naive `TOP N ... WHERE Stamp > cursor` loop that advances the cursor to the last
row's Stamp would either skip sibling rows that didn't fit on that page, or — if a single
Stamp's rows outnumber one page — loop forever on the same page. Paginating by the
compound key `(Stamp, Code)` instead avoids both failure modes: every row is visited
exactly once regardless of how many rows share a Stamp.

The persisted checkpoint in `sync_state` stays a single `last_stamp` value (PRD §5's
schema) — that's safe because a caller only starts a new sync after this function has
fully exhausted the previous one, i.e. every row at the boundary Stamp was already seen.
"""

from app.busy.client import BusyClient
from app.busy.xml_util import parse_rowset_xml


async def fetch_all_pages(
    client: BusyClient,
    *,
    select_columns: list[str],
    from_and_where: str,
    since: int,
    page_size: int,
) -> list[dict[str, str]]:
    """Run `from_and_where` (e.g. ``"Master1 WHERE MasterType = 6"``), paginated by
    `(Stamp, Code)` starting after `since`, until fully exhausted. `select_columns` must
    include ``"Stamp"`` and ``"Code"`` — they drive the pagination cursor."""
    if "Stamp" not in select_columns or "Code" not in select_columns:
        raise ValueError("select_columns must include 'Stamp' and 'Code' for pagination")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    columns_sql = ", ".join(select_columns)
    all_rows: list[dict[str, str]] = []
    cursor_stamp = since
    cursor_code: int | None = None

    while True:
        if cursor_code is None:
            predicate = f"Stamp > {cursor_stamp}"
        else:
            predicate = (
                f"(Stamp > {cursor_stamp} OR (Stamp = {cursor_stamp} AND Code > {cursor_code}))"
            )
        sql = (
            f"SELECT TOP {page_size} {columns_sql} FROM {from_and_where} "
            f"AND {predicate} ORDER BY Stamp, Code"
        )
        xml = await client.run_query(sql)
        page = parse_rowset_xml(xml)
        if not page:
            break

        all_rows.extend(page)
        last = page[-1]
        cursor_stamp = int(last["Stamp"])
        cursor_code = int(last["Code"])
        if len(page) < page_size:
            break

    return all_rows
