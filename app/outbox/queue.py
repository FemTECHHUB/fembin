"""Enqueue side of the outbox — a plain local DB insert, no BUSY call, so it's always
safe to call inline from a request handler (unlike the worker's draining side)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.outbox.models import OutboxJob, OutboxStatus


def enqueue(
    session: Session, *, job_type: str, payload: dict[str, Any], idempotency_key: str
) -> OutboxJob:
    """Insert a queued job, or return the existing one for this idempotency key unchanged
    — a retried request must never double-post (CLAUDE.md §2.2)."""
    existing = session.scalar(select(OutboxJob).where(OutboxJob.idempotency_key == idempotency_key))
    if existing is not None:
        return existing

    job = OutboxJob(
        job_type=job_type,
        payload=payload,
        status=OutboxStatus.QUEUED,
        idempotency_key=idempotency_key,
    )
    session.add(job)
    session.commit()
    return job
