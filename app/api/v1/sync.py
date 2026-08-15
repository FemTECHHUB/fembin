"""Catalog sync ops endpoints — thin (CLAUDE.md §3). The trigger endpoint never calls BUSY
inline: it hands the job to FastAPI's BackgroundTasks so the HTTP response returns before
any BUSY call happens (Sprint 1 DoD — no endpoint calls BUSY synchronously in a request)."""

from fastapi import APIRouter, BackgroundTasks

from app.api.v1.deps import DbSession, SettingsDep
from app.api.v1.schemas import (
    SyncRequest,
    SyncStatusEntryOut,
    SyncStatusResponse,
    SyncTriggerResponse,
    WooSyncStatusOut,
)
from app.db.session import SessionLocal
from app.domain.catalog.queries import get_sync_status
from app.domain.catalog.scheduler import run_catalog_sync
from app.domain.catalog.woo_sync import get_woo_sync_state

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
