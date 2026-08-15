"""Scheduler-level test — Sprint 1 DoD: "First full sync and an immediate re-sync are
both timed and logged — the second must show near-zero BUSY calls." `db_session` is
depended on only for its table-cleanup side effect; run_catalog_sync opens its own
sessions from the same SessionLocal/engine.
"""

import logging

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import SessionLocal
from app.domain.catalog.scheduler import run_catalog_sync


async def test_run_catalog_sync_logs_timing_for_full_and_noop_resync(
    db_session: Session, busy_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.domain.catalog.scheduler")

    first_results = await run_catalog_sync(SessionLocal, busy_settings, full=True)
    second_results = await run_catalog_sync(SessionLocal, busy_settings, full=False)

    assert {r.entity: r.changed for r in first_results} == {"material_centers": 2, "products": 8}
    assert {r.entity: r.changed for r in second_results} == {"material_centers": 0, "products": 0}

    # 2 entities x 2 runs = 4 timed, logged sync results.
    assert caplog.text.count("elapsed=") == 4
