"""Catalog sync ops endpoints — thin (CLAUDE.md §3). The trigger endpoint never calls BUSY
inline: it hands the job to FastAPI's BackgroundTasks so the HTTP response returns before
any BUSY call happens (Sprint 1 DoD — no endpoint calls BUSY synchronously in a request).

The WooCommerce push endpoint below is the one exception to "never call an external
service inline": it never touches BUSY (only WooCommerce, a normal REST API, not BUSY's
single-instance/no-proven-concurrency desktop app), and a "push these products now" button
needs an immediate per-product result to show, not a fire-and-forget 202."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.v1.deps import DbSession, SettingsDep, SuperadminUser
from app.api.v1.schemas import (
    SyncRequest,
    SyncStatusEntryOut,
    SyncStatusResponse,
    SyncTriggerResponse,
    WooPushItemOut,
    WooPushRequest,
    WooPushResponse,
    WooSyncStatusOut,
)
from app.db.session import SessionLocal
from app.domain.catalog.queries import get_sync_status
from app.domain.catalog.scheduler import run_catalog_sync
from app.domain.catalog.woo_sync import get_woo_sync_state, push_products_by_code
from app.integrations.woocommerce import WooCommerceClient

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/products", response_model=SyncTriggerResponse, status_code=202)
def trigger_products_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
) -> SyncTriggerResponse:
    background_tasks.add_task(run_catalog_sync, SessionLocal, settings, full=body.full)
    return SyncTriggerResponse(status="scheduled")


@router.get("/status", response_model=SyncStatusResponse)
def sync_status_route(db: DbSession) -> SyncStatusResponse:
    busy_entries = get_sync_status(db)
    woo_state = get_woo_sync_state(db)
    db.commit()  # get_woo_sync_state may have inserted the singleton row on first call
    return SyncStatusResponse(
        busy=[SyncStatusEntryOut.model_validate(e, from_attributes=True) for e in busy_entries],
        woocommerce=WooSyncStatusOut.model_validate(woo_state),
    )


@router.post("/woocommerce/push", response_model=WooPushResponse)
async def push_to_woocommerce_route(
    body: WooPushRequest, db: DbSession, settings: SettingsDep, _: SuperadminUser
) -> WooPushResponse:
    """Push specifically chosen products to the live website now — superadmin-only (this
    is an immediate, real write to a public site, not a local/reversible action)."""
    if not settings.woo_site_url:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "WooCommerce isn't configured (WOO_SITE_URL is blank) — nothing to push to yet.",
        )
    async with WooCommerceClient.from_settings(settings) as woo:
        results = await push_products_by_code(
            db, woo, body.busy_codes, new_product_status=settings.woo_new_product_status
        )
    return WooPushResponse(
        results=[
            WooPushItemOut(busy_code=r.busy_code, name=r.name, action=r.action, error=r.error)
            for r in results
        ]
    )
