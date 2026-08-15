#!/usr/bin/env python3
"""Pull every Sale Quotation ever enqueued and log each one with its status — an ops
visibility tool (GET /api/v1/quotations serves the same data over HTTP; this is for
watching the structured logs directly).

Status meanings: "queued" = not yet posted to BUSY, "running" = the worker is posting
it right now, "done" = posted — the BUSY-assigned VchNo/VchCode are in the result,
"failed" = BUSY rejected it or the worker errored — see last_error.

Usage: uv run python scripts/list_quotations.py
"""

import logging

from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.orders.quotations import list_quotations
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.list_quotations")


def main() -> None:
    setup_logging(get_settings().log_level)

    session = SessionLocal()
    try:
        jobs = list_quotations(session)
        for job in jobs:
            result = job.result or {}
            logger.info(
                "quotation id=%d status=%s attempts=%d vch_no=%s vch_code=%s "
                "last_error=%r created_at=%s",
                job.id,
                job.status,
                job.attempts,
                result.get("vch_no"),
                result.get("vch_code"),
                job.last_error,
                job.created_at,
            )
        by_status: dict[str, int] = {}
        for job in jobs:
            by_status[job.status] = by_status.get(job.status, 0) + 1
        logger.info("quotation listing done: total=%d by_status=%s", len(jobs), by_status)
    finally:
        session.close()


if __name__ == "__main__":
    main()
