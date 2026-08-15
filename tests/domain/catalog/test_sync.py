"""Domain-level catalog sync tests against the mock BUSY server + a real local MySQL
(tests/domain/catalog/conftest.py). Covers three Sprint 1 DoD items directly:

  - pagination, exercised again at the domain level (not just app/busy/pagination.py)
  - a blocked/deactivated BUSY record ends up is_active=False locally, never deleted
  - a full sync followed immediately by an incremental re-sync shows near-zero change
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.db.models import Product
from app.domain.catalog.sync import get_last_stamp, sync_material_centers, sync_products


async def test_sync_products_paginates_and_marks_blocked_item_inactive(
    db_session: Session, busy_client: BusyClient
) -> None:
    result = await sync_products(db_session, busy_client, full=True, page_size=3)

    # 8 rows from the mock's paginatable Item dataset (tests/fixtures/mock_busy.py),
    # only reachable across 3 pages at page_size=3 with its deliberate Stamp ties.
    assert result.changed == 8
    assert result.stored == 8
    assert result.failed == 0

    products = {p.busy_code: p for p in db_session.scalars(select(Product))}
    assert set(products) == {301, 302, 303, 304, 305, 306, 307, 308}

    # Code 308 is the blocked one in the fixture dataset — marked inactive, not deleted.
    blocked = products[308]
    assert blocked.is_active is False

    # Everything else came from the (mocked) GetMasterXML detail call and is active.
    active = products[301]
    assert active.is_active is True
    assert active.name == "Fake Item 301"
    assert active.price == 1000


async def test_full_sync_then_immediate_resync_is_near_zero(
    db_session: Session, busy_client: BusyClient
) -> None:
    first = await sync_products(db_session, busy_client, full=True, page_size=3)
    assert first.changed == 8

    # Immediately re-run, incrementally — nothing in the mock dataset changed, so this
    # must find zero rows, mirroring the prototype's proven "17.3s full -> 2.2s no-op" result.
    second = await sync_products(db_session, busy_client, full=False, page_size=3)
    assert second.changed == 0
    assert second.stored == 0
    assert second.incremental is True

    # The checkpoint itself didn't regress just because nothing changed.
    assert get_last_stamp(db_session, "products") == 40


async def test_sync_material_centers_full_then_incremental_is_near_zero(
    db_session: Session, busy_client: BusyClient
) -> None:
    first = await sync_material_centers(db_session, busy_client, full=True)
    assert first.changed == 2
    assert first.incremental is False

    second = await sync_material_centers(db_session, busy_client, full=False)
    assert second.changed == 0
    assert second.incremental is True
