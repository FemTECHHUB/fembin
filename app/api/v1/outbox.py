"""Outbox job status route — thin (CLAUDE.md §3). How a caller finds out what actually
happened to something it enqueued (e.g. the BUSY-assigned VchCode for a quotation)."""

from fastapi import APIRouter, HTTPException

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas_outbox import OutboxJobOut
from app.outbox.models import OutboxJob

router = APIRouter(prefix="/outbox", tags=["outbox"])


@router.get("/{job_id}", response_model=OutboxJobOut)
def get_outbox_job_route(job_id: int, db: DbSession, current_user: CurrentUser) -> OutboxJobOut:
    job = db.get(OutboxJob, job_id)
    # `job_id` is a sequential integer — trivially enumerable. Without this check, any
    # authenticated caller could read any other branch's customer name/phone/pricing by
    # just incrementing the ID. 404 (not 403) for a real job outside the caller's own
    # branch too — same reasoning as a missing job, so probing IDs can't distinguish
    # "doesn't exist" from "exists but isn't yours".
    if job is None or (
        not current_user.is_superadmin
        and job.payload.get("material_center_code") != current_user.material_center_code
    ):
        raise HTTPException(status_code=404, detail="Outbox job not found")
    return OutboxJobOut.model_validate(job)
