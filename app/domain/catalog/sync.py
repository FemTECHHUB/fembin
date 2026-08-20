"""BUSY -> MySQL catalog sync: material centers and products (items).

Every fetch defaults to incremental via BUSY's `Stamp` checkpoint, only advanced after a
successful commit to our own tables (CLAUDE.md §2.3), and pages through BUSY's Stamp-coarse
changelog safely (app/busy/pagination.py). Blocked/deactivated records are marked
`is_active=False`, never deleted (CLAUDE.md §2.4) — the real bug this guards against is
described there.

Each `sync_*` function is one complete transaction: either every row from this run and the
new checkpoint land together, or (on an uncaught exception) nothing does. Domain logic only
— never called from an API request handler directly (CLAUDE.md §2.1); see
app/domain/catalog/scheduler.py for how these get triggered.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.busy.bit_columns import is_master_active
from app.busy.client import BusyClient, BusyError
from app.busy.constants import MasterType
from app.busy.pagination import fetch_all_pages
from app.busy.xml_util import XmlValue, parse_element_xml
from app.db.models import Category, MaterialCenter, Product, Salesman, SyncState

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 500
UNCATEGORISED = "Uncategorised"


@dataclass(frozen=True)
class SyncResult:
    entity: str
    changed: int
    incremental: bool
    stored: int = 0
    failed: int = 0


def get_last_stamp(session: Session, entity: str) -> int:
    row = session.get(SyncState, entity)
    return row.last_stamp if row is not None else 0


def _set_last_stamp(session: Session, entity: str, stamp: int) -> None:
    stmt = mysql_insert(SyncState).values(entity=entity, last_stamp=stamp)
    stmt = stmt.on_duplicate_key_update(last_stamp=stmt.inserted.last_stamp, updated_at=func.now())
    session.execute(stmt)


def _upsert_category(session: Session, busy_group_name: str) -> None:
    stmt = mysql_insert(Category).values(busy_group_name=busy_group_name)
    stmt = stmt.on_duplicate_key_update(busy_group_name=stmt.inserted.busy_group_name)
    session.execute(stmt)


async def sync_material_centers(
    session: Session,
    client: BusyClient,
    *,
    full: bool = False,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> SyncResult:
    """MasterType=11 — stores/branches. Bulk SQL only, no per-record detail calls."""
    entity = "material_centers"
    since = -1 if full else get_last_stamp(session, entity)
    rows = await fetch_all_pages(
        client,
        select_columns=[
            "Code",
            "Name",
            "Alias",
            "ParentGrp",
            "Stamp",
            "BlockedMaster",
            "DeactiveMaster",
        ],
        from_and_where=f"Master1 WHERE MasterType = {int(MasterType.MATERIAL_CENTER)}",
        since=since,
        page_size=page_size,
    )

    max_stamp = since
    for row in rows:
        stmt = mysql_insert(MaterialCenter).values(
            busy_code=int(row["Code"]),
            name=row["Name"],
            alias=row.get("Alias") or None,
            parent_group=row.get("ParentGrp") or None,
            is_active=is_master_active(row),
        )
        stmt = stmt.on_duplicate_key_update(
            name=stmt.inserted.name,
            alias=stmt.inserted.alias,
            parent_group=stmt.inserted.parent_group,
            is_active=stmt.inserted.is_active,
            updated_at=func.now(),
        )
        session.execute(stmt)
        max_stamp = max(max_stamp, int(row["Stamp"]))

    _set_last_stamp(session, entity, max_stamp)
    session.commit()
    return SyncResult(entity=entity, changed=len(rows), incremental=not full, stored=len(rows))


async def sync_salesmen(
    session: Session,
    client: BusyClient,
    *,
    full: bool = False,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> SyncResult:
    """MasterType=19 — "Broker" in BUSY's generic schema, but **this company relabels it
    "Engineer"** (a repair-shop's equivalent of a sales rep — confirmed live 2026-08-20 via
    a screenshot of BUSY's own "List of Engineer" GUI screen: all 13 real names + aliases
    matched exactly against `SELECT Name, Alias FROM Master1 WHERE MasterType=19`).

    `MasterType=33` ("Executive", genuinely BUSY's own "Salesmen" label) was tried first —
    it's real, but genuinely empty for this company (confirmed both in the original
    research phase and again live here), because this business uses the repurposed Broker
    master instead. This mapping is company-specific configuration, not a BUSY constant —
    a different BUSY company could easily use MasterType=33 as intended, or something else
    entirely. Re-verify before assuming MasterType=19 elsewhere (CLAUDE.md §8)."""
    entity = "salesmen"
    since = -1 if full else get_last_stamp(session, entity)
    rows = await fetch_all_pages(
        client,
        select_columns=[
            "Code",
            "Name",
            "Alias",
            "ParentGrp",
            "Stamp",
            "BlockedMaster",
            "DeactiveMaster",
        ],
        from_and_where=f"Master1 WHERE MasterType = {int(MasterType.BROKER)}",
        since=since,
        page_size=page_size,
    )

    max_stamp = since
    for row in rows:
        stmt = mysql_insert(Salesman).values(
            busy_code=int(row["Code"]),
            name=row["Name"],
            alias=row.get("Alias") or None,
            parent_group=row.get("ParentGrp") or None,
            is_active=is_master_active(row),
        )
        stmt = stmt.on_duplicate_key_update(
            name=stmt.inserted.name,
            alias=stmt.inserted.alias,
            parent_group=stmt.inserted.parent_group,
            is_active=stmt.inserted.is_active,
            updated_at=func.now(),
        )
        session.execute(stmt)
        max_stamp = max(max_stamp, int(row["Stamp"]))

    _set_last_stamp(session, entity, max_stamp)
    session.commit()
    return SyncResult(entity=entity, changed=len(rows), incremental=not full, stored=len(rows))


@dataclass(frozen=True)
class _ItemDetail:
    name: str
    price: Decimal
    unit: str
    item_group: str
    tracks_stock: bool


def _map_item_fields(parsed: XmlValue, *, code: int) -> _ItemDetail:
    """Confirmed real Item field names (CLAUDE.md §8 / docs/reference/12-schema-findings.md)
    — do not re-guess these (`Price`/`Unit`/`ItemGroup` were earlier, wrong guesses)."""
    node: XmlValue | list[XmlValue] = parsed
    if isinstance(node, dict) and "Item" in node:
        node = node["Item"]
    if not isinstance(node, dict):
        raise ValueError(f"Unexpected GetMasterXML shape for item {code}")
    item = node
    return _ItemDetail(
        name=str(item.get("Name", "")),
        price=Decimal(str(item.get("SalePrice") or 0)),
        unit=str(item.get("MainUnit") or ""),
        item_group=str(item.get("ParentGroup") or UNCATEGORISED),
        tracks_stock=item.get("DoNotMaintainStkBal") != "True",
    )


async def sync_products(
    session: Session,
    client: BusyClient,
    *,
    full: bool = False,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> SyncResult:
    """MasterType=6 — Items. One GetMasterXML call per *changed, active* item for the real
    fields; newly-blocked items are marked inactive without a detail call at all — nothing
    to fetch. Stock is deliberately not synced (PRD §5 non-goal, unsolved problem)."""
    entity = "products"
    since = -1 if full else get_last_stamp(session, entity)
    changed = await fetch_all_pages(
        client,
        select_columns=["Code", "Name", "Stamp", "BlockedMaster", "DeactiveMaster"],
        from_and_where=f"Master1 WHERE MasterType = {int(MasterType.ITEM)}",
        since=since,
        page_size=page_size,
    )

    _upsert_category(session, UNCATEGORISED)

    max_stamp = since
    stored = 0
    failed = 0
    for row in changed:
        code = int(row["Code"])
        max_stamp = max(max_stamp, int(row["Stamp"]))

        if not is_master_active(row):
            stmt = mysql_insert(Product).values(
                busy_code=code,
                name=row["Name"],
                price=Decimal("0"),
                unit="",
                item_group=UNCATEGORISED,
                tracks_stock=False,
                is_active=False,
            )
            stmt = stmt.on_duplicate_key_update(
                name=stmt.inserted.name,
                is_active=stmt.inserted.is_active,
                updated_at=func.now(),
            )
            session.execute(stmt)
            stored += 1
            continue

        try:
            detail_xml = await client.get_master_xml(code)
            detail = _map_item_fields(parse_element_xml(detail_xml), code=code)
        except (BusyError, httpx.HTTPError, ValueError) as exc:
            logger.warning("GetMasterXML failed for item %s: %s", code, exc)
            failed += 1
            continue

        _upsert_category(session, detail.item_group)
        stmt = mysql_insert(Product).values(
            busy_code=code,
            name=detail.name,
            price=detail.price,
            unit=detail.unit,
            item_group=detail.item_group,
            tracks_stock=detail.tracks_stock,
            is_active=True,
        )
        stmt = stmt.on_duplicate_key_update(
            name=stmt.inserted.name,
            price=stmt.inserted.price,
            unit=stmt.inserted.unit,
            item_group=stmt.inserted.item_group,
            tracks_stock=stmt.inserted.tracks_stock,
            is_active=stmt.inserted.is_active,
            updated_at=func.now(),
        )
        session.execute(stmt)
        stored += 1

    _set_last_stamp(session, entity, max_stamp)
    session.commit()
    return SyncResult(
        entity=entity, changed=len(changed), incremental=not full, stored=stored, failed=failed
    )
