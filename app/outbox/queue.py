"""Enqueue side of the outbox — a plain local DB insert, no BUSY call, so it's always
safe to call inline from a request handler (unlike the worker's draining side)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.outbox.models import OutboxJob, OutboxStatus


def enqueue(
    session: Session, *, job_type: str, payload: dict[str, Any], idempotency_key: str
) -> OutboxJob:
    """Insert a queued job, or return the existing one for this idempotency key unchanged
    — a retried request must never double-post (CLAUDE.md §2.2).

    The existence check below is check-then-insert, not atomic — two concurrent requests
    with the same idempotency_key (a double-submitted form, a frontend retry on a flaky
    connection) can both pass it before either commits. The column's `unique=True`
    constraint (app/outbox/models.py) still guarantees only one row ever lands — it's
    correctness that was never at risk — but without catching the loser's `IntegrityError`
    here, that caller would get an unhandled 500 instead of the idempotent "here's your
    existing job" response this function exists to provide. Confirmed live 2026-10-16 as a
    real gap, not just theoretical, during a production-readiness audit."""
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
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(OutboxJob).where(OutboxJob.idempotency_key == idempotency_key)
        )
        if existing is None:
            raise  # the conflict wasn't this key after all — a real, different problem
        return existing
    return job
