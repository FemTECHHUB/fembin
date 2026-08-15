"""Drains the outbox queue — the only place BUSY writes actually happen (CLAUDE.md §2.2).

Single-threaded, no concurrency: BUSY is one instance with no proven write concurrency —
do not casually add a worker pool without re-reading PRD §11's open question on that. The
select-then-update claim below is only race-free because of that single-worker assumption.

Failed jobs are NOT automatically retried by the periodic loop (they're left in
`FAILED`, not put back to `QUEUED`) — that's deliberately out of scope here; PRD §6
designs a `POST /api/v1/admin/queue/{job_id}/retry` for that, which needs the
still-missing auth story (see docs/sprints/sprint-01-busy-read-layer.md) before it should
be exposed over HTTP.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.config import Settings
from app.outbox.models import OutboxJob, OutboxStatus

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, Any], BusyClient], Awaitable[dict[str, Any]]]


_HANDLERS: dict[str, JobHandler] = {}


def register_handler(job_type: str, handler: JobHandler) -> None:
    """Domain modules register their own job handlers here at import time (e.g.
    app/domain/orders/quotations.py registers "add_sale_quotation") rather than this
    module importing domain code — keeps the dependency direction domain -> outbox,
    never outbox -> domain (CLAUDE.md §2.1, one direction of dependency)."""
    _HANDLERS[job_type] = handler


async def _handle_add_voucher(payload: dict[str, Any], busy: BusyClient) -> dict[str, Any]:
    """Generic: the payload already carries a fully-built VchXml, so this needs no
    domain knowledge and stays built in rather than registered."""
    vch_code = await busy.add_voucher(int(payload["vch_type"]), str(payload["vch_xml"]))
    return {"vch_code": vch_code}


register_handler("add_voucher", _handle_add_voucher)


async def process_next_job(session: Session, busy: BusyClient) -> OutboxJob | None:
    """Claim and process one queued job, oldest first. Returns None if the queue is empty."""
    job = session.scalar(
        select(OutboxJob)
        .where(OutboxJob.status == OutboxStatus.QUEUED)
        .order_by(OutboxJob.id)
        .limit(1)
    )
    if job is None:
        return None

    job.status = OutboxStatus.RUNNING
    job.attempts += 1
    session.commit()

    handler = _HANDLERS.get(job.job_type)
    if handler is None:
        job.status = OutboxStatus.FAILED
        job.last_error = f"Unknown job_type: {job.job_type}"
        session.commit()
        logger.error("Outbox job %s: unknown job_type %s", job.id, job.job_type)
        return job

    try:
        result = await handler(job.payload, busy)
    except Exception as exc:
        job.status = OutboxStatus.FAILED
        job.last_error = str(exc)
        session.commit()
        logger.warning("Outbox job %s (%s) failed: %s", job.id, job.job_type, exc)
        return job

    job.status = OutboxStatus.DONE
    job.result = result
    session.commit()
    logger.info("Outbox job %s (%s) done: %s", job.id, job.job_type, result)
    return job


async def drain_outbox(session_factory: Callable[[], Session], settings: Settings) -> int:
    """Process every currently-queued job, oldest first. Returns how many were processed."""
    processed = 0
    async with BusyClient.from_settings(settings) as busy:
        while True:
            session = session_factory()
            try:
                job = await process_next_job(session, busy)
            finally:
                session.close()
            if job is None:
                break
            processed += 1
    return processed


async def outbox_worker_loop(
    session_factory: Callable[[], Session],
    settings: Settings,
    *,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """Periodic drain — the actual outbox worker CLAUDE.md §2.2 requires."""
    while not stop_event.is_set():
        try:
            await drain_outbox(session_factory, settings)
        except Exception:
            logger.exception("Outbox drain failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
