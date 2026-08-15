"""Background sync trigger — the seed of the eventual outbox worker (CLAUDE.md §2.2 will
formalize this once BUSY *writes* enter the picture in Sprint 3/4). For now this is the
only place in the app that calls BUSY; API request handlers only ever read MySQL
(Sprint 1 DoD).
"""

import asyncio
import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.domain.catalog.sync import SyncResult, sync_material_centers, sync_products

logger = logging.getLogger(__name__)


async def run_catalog_sync(
    session_factory: Callable[[], Session], settings: Settings, *, full: bool = False
) -> list[SyncResult]:
    """Run one full catalog sync pass (material centers, then products). Each entity is
    its own DB transaction (app/domain/catalog/sync.py) — a failure in one doesn't roll
    back the other. Timed and logged per entity — this is how the "full sync then
    near-zero no-op re-sync" proof (Sprint 1 DoD) gets verified."""
    results: list[SyncResult] = []
    async with BusyClient.from_settings(settings) as client:
        for sync_fn in (sync_material_centers, sync_products):
            session = session_factory()
            start = time.monotonic()
            try:
                result = await sync_fn(session, client, full=full)
            except Exception:
                session.rollback()
                logger.exception("Catalog sync failed for %s", sync_fn.__name__)
                raise
            finally:
                session.close()
            elapsed = time.monotonic() - start
            logger.info(
                "Catalog sync: entity=%s changed=%d stored=%d failed=%d "
                "incremental=%s elapsed=%.2fs",
                result.entity,
                result.changed,
                result.stored,
                result.failed,
                result.incremental,
                elapsed,
            )
            results.append(result)
    return results


async def catalog_sync_loop(
    session_factory: Callable[[], Session],
    settings: Settings,
    *,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """Periodic trigger. Doesn't need to be the full outbox system yet (Sprint 1 scope) —
    just proves incremental sync can run unattended."""
    while not stop_event.is_set():
        try:
            await run_catalog_sync(session_factory, settings)
        except Exception:
            logger.exception("Scheduled catalog sync run failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
