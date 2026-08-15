"""app/outbox/queue.py — idempotency is the core correctness requirement (CLAUDE.md §2.2):
a retried request must never double-post."""

from sqlalchemy.orm import Session

from app.outbox.models import OutboxJob, OutboxStatus
from app.outbox.queue import enqueue


def test_enqueue_creates_a_queued_job(db_session: Session) -> None:
    job = enqueue(db_session, job_type="add_voucher", payload={"a": 1}, idempotency_key="k1")
    assert job.status == OutboxStatus.QUEUED
    assert job.attempts == 0
    assert job.payload == {"a": 1}


def test_enqueue_is_idempotent_on_retry(db_session: Session) -> None:
    first = enqueue(db_session, job_type="add_voucher", payload={"a": 1}, idempotency_key="dup")
    second = enqueue(db_session, job_type="add_voucher", payload={"a": 2}, idempotency_key="dup")

    assert first.id == second.id
    assert second.payload == {"a": 1}  # the original wins — retry doesn't overwrite it

    count = db_session.query(OutboxJob).filter_by(idempotency_key="dup").count()
    assert count == 1
