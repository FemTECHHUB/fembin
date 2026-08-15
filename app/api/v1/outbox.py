"""Outbox job status route — thin (CLAUDE.md §3). How a caller finds out what actually
happened to something it enqueued (e.g. the BUSY-assigned VchCode for a quotation)."""

from fastapi import APIRouter, HTTPException

from app.api.v1.deps import DbSession
from app.api.v1.schemas_outbox import OutboxJobOut
from app.outbox.models import OutboxJob

router = APIRouter(prefix="/outbox", tags=["outbox"])


@router.get("/{job_id}", response_model=OutboxJobOut)
def get_outbox_job_route(job_id: int, db: DbSession) -> OutboxJobOut:
    job = db.get(OutboxJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Outbox job not found")
    return OutboxJobOut.model_validate(job)
