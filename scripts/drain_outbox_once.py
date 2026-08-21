#!/usr/bin/env python3
"""Process every currently-queued outbox job once, then exit — for cron, not a
long-running loop.

Why this exists: `OUTBOX_WORKER_ENABLED=true` runs the worker as a background asyncio
task inside the app process (app/main.py's lifespan). That's fine for a VPS/Docker
deployment where the process stays up, but a cPanel/Passenger app isn't guaranteed to
stay resident — Passenger can idle or recycle the process, silently stopping the worker
with it. On cPanel, leave OUTBOX_WORKER_ENABLED=false and instead point a cPanel Cron Job
at this script (e.g. every minute) — CLAUDE.md §2.2's queue is what makes that safe: a
missed or overlapping run just leaves jobs QUEUED a little longer, never double-posts
(idempotency_key) or loses one.

Usage: uv run python scripts/drain_outbox_once.py
   or: /home/<user>/virtualenv/<app>/3.12/bin/python scripts/drain_outbox_once.py
"""

import asyncio
import logging

from app.config import get_settings
from app.db.session import SessionLocal
from app.logging_config import setup_logging
from app.outbox.worker import drain_outbox

logger = logging.getLogger("scripts.drain_outbox_once")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    processed = asyncio.run(drain_outbox(SessionLocal, settings))
    logger.info("drain_outbox_once: processed=%d", processed)


if __name__ == "__main__":
    main()
