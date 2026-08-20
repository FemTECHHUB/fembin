"""app/outbox/worker.py — processes queued jobs against BUSY (mocked here), single job
at a time, oldest first. Uses the mock BUSY server's SC=2 support (tests/fixtures/mock_busy.py):
"FORCE_FAIL" anywhere in VchXml simulates a BUSY-side rejection.
"""

from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.db.session import SessionLocal
from app.outbox.models import OutboxStatus
from app.outbox.queue import enqueue
from app.outbox.worker import drain_outbox, process_next_job, register_handler


async def test_process_next_job_success(db_session: Session, busy_client: BusyClient) -> None:
    job = enqueue(
        db_session,
        job_type="add_voucher",
        payload={"vch_type": 26, "vch_xml": "<SaleQuotation/>"},
        idempotency_key="q1",
    )

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.id == job.id
    assert processed.status == OutboxStatus.DONE
    assert processed.attempts == 1
    assert processed.result is not None
    assert "vch_code" in processed.result


async def test_process_next_job_failure_is_recorded(
    db_session: Session, busy_client: BusyClient
) -> None:
    enqueue(
        db_session,
        job_type="add_voucher",
        payload={"vch_type": 26, "vch_xml": "FORCE_FAIL"},
        idempotency_key="q2",
    )

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.FAILED
    assert processed.last_error is not None


async def test_process_next_job_unknown_job_type_fails(
    db_session: Session, busy_client: BusyClient
) -> None:
    enqueue(db_session, job_type="mystery", payload={}, idempotency_key="q3")

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.FAILED
    assert "Unknown job_type" in (processed.last_error or "")


async def test_process_next_job_records_exception_type_when_message_is_empty(
    db_session: Session, busy_client: BusyClient
) -> None:
    """httpx connect/read timeouts (and asyncio.TimeoutError) can have an empty str() —
    a bare `str(exc)` would silently leave `last_error` useless (real bug, seen live
    2026-08-20: a job that failed on a genuine BUSY connectivity timeout recorded ""
    instead of any diagnosable message)."""

    async def _raise_empty(payload: dict[str, object], busy: BusyClient) -> dict[str, object]:
        raise TimeoutError()

    register_handler("test_empty_error", _raise_empty)
    enqueue(db_session, job_type="test_empty_error", payload={}, idempotency_key="q-empty")

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.FAILED
    assert processed.last_error == "TimeoutError"


async def test_process_next_job_empty_queue_returns_none(
    db_session: Session, busy_client: BusyClient
) -> None:
    assert await process_next_job(db_session, busy_client) is None


async def test_drain_outbox_processes_all_queued_jobs(
    db_session: Session, busy_settings: Settings
) -> None:
    for i in range(3):
        enqueue(
            db_session,
            job_type="add_voucher",
            payload={"vch_type": 26, "vch_xml": f"<SaleQuotation><N>{i}</N></SaleQuotation>"},
            idempotency_key=f"drain-{i}",
        )

    processed_count = await drain_outbox(SessionLocal, busy_settings)

    assert processed_count == 3
