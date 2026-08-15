"""Catalog sync ops endpoints — thin (CLAUDE.md §3). The trigger endpoint never calls BUSY
inline: it hands the job to FastAPI's BackgroundTasks so the HTTP response returns before
any BUSY call happens (Sprint 1 DoD — no endpoint calls BUSY synchronously in a request)."""

from fastapi import APIRouter, BackgroundTasks

from app.api.v1.deps import DbSession, SettingsDep
from app.api.v1.schemas import SyncRequest, SyncStatusEntryOut, SyncTriggerResponse
from app.db.session import SessionLocal
from app.domain.catalog.queries import get_sync_status
from app.domain.catalog.scheduler import run_catalog_sync

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/products", response_model=SyncTriggerResponse, status_code=202)
def trigger_products_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
) -> SyncTriggerResponse:
    background_tasks.add_task(run_catalog_sync, SessionLocal, settings, full=body.full)
    return SyncTriggerResponse(status="scheduled")


@router.get("/status", response_model=list[SyncStatusEntryOut])
def sync_status_route(db: DbSession) -> list[SyncStatusEntryOut]:
    entries = get_sync_status(db)
    return [SyncStatusEntryOut.model_validate(e, from_attributes=True) for e in entries]
