"""Scheduler-level test — Sprint 1 DoD: "First full sync and an immediate re-sync are
both timed and logged — the second must show near-zero BUSY calls." `db_session` is
depended on only for its table-cleanup side effect; run_catalog_sync opens its own
sessions from the same SessionLocal/engine. Also covers Sprint 2's wiring: the
WooCommerce push runs as a third step, in seed mode by default (zero WooCommerce calls
until explicitly opted in — see test_woo_sync.py for that behavior in detail).
"""

import logging

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import SessionLocal
from app.domain.catalog.scheduler import run_catalog_sync


async def test_run_catalog_sync_logs_timing_for_full_and_noop_resync(
    db_session: Session, catalog_sync_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.domain.catalog.scheduler")

    first = await run_catalog_sync(SessionLocal, catalog_sync_settings, full=True)
    second = await run_catalog_sync(SessionLocal, catalog_sync_settings, full=False)

    assert {r.entity: r.changed for r in first.busy} == {"material_centers": 2, "products": 8}
    assert {r.entity: r.changed for r in second.busy} == {"material_centers": 0, "products": 0}

    # Woo isn't seeded yet by default — zero WooCommerce calls both runs, but the 7 active
    # products (code 308 is the blocked one) are still recorded as "seen".
    assert first.woo is not None
    assert (first.woo.seeded, first.woo.created) == (7, 0)
    assert second.woo is not None
    assert (second.woo.seeded, second.woo.created) == (7, 0)

    # 3 steps (material_centers, products, woocommerce) x 2 runs = 6 timed, logged results.
    assert caplog.text.count("elapsed=") == 6
