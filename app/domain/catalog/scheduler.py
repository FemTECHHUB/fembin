"""Background sync trigger — the seed of the eventual outbox worker (CLAUDE.md §2.2 will
formalize this once BUSY *writes* enter the picture in Sprint 3/4). For now this is the
only place in the app that calls BUSY; API request handlers only ever read MySQL
(Sprint 1 DoD).
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.domain.catalog.sync import SyncResult, sync_material_centers, sync_products
from app.domain.catalog.woo_sync import WooPushResult, push_products_to_woocommerce
from app.integrations.woocommerce import WooCommerceClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogSyncRunResult:
    busy: list[SyncResult]
    woo: WooPushResult | None


async def run_catalog_sync(
    session_factory: Callable[[], Session], settings: Settings, *, full: bool = False
) -> CatalogSyncRunResult:
    """Run one full catalog sync pass: BUSY pull (material centers, then products), then
    a WooCommerce push (Sprint 2) — skipped entirely, not failed, if WooCommerce isn't
    configured (`woo_site_url` blank). Each step is its own DB transaction
    (app/domain/catalog/sync.py, app/domain/catalog/woo_sync.py) — a failure in one
    doesn't roll back the others. Timed and logged per step — this is how the "full sync
    then near-zero no-op re-sync" proof (Sprint 1 DoD) gets verified."""
    busy_results: list[SyncResult] = []
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
            busy_results.append(result)

    woo_result: WooPushResult | None = None
    if settings.woo_site_url:
        session = session_factory()
        start = time.monotonic()
        try:
            async with WooCommerceClient.from_settings(settings) as woo:
                woo_result = await push_products_to_woocommerce(
                    session, woo, new_product_status=settings.woo_new_product_status
                )
        except Exception:
            session.rollback()
            logger.exception("WooCommerce push failed")
            raise
        finally:
            session.close()
        elapsed = time.monotonic() - start
        logger.info(
            "Catalog sync: entity=woocommerce seeded=%d created=%d updated=%d "
            "skipped=%d failed=%d elapsed=%.2fs",
            woo_result.seeded,
            woo_result.created,
            woo_result.updated,
            woo_result.skipped,
            woo_result.failed,
            elapsed,
        )
    else:
        logger.info("Catalog sync: WooCommerce not configured, skipping push")

    return CatalogSyncRunResult(busy=busy_results, woo=woo_result)


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
