#!/usr/bin/env python3
"""Run one catalog sync pass (material centers, products, salesmen, WooCommerce push),
then exit — for cron, same reasoning as drain_outbox_once.py: don't rely on
CATALOG_SYNC_ENABLED's in-process loop surviving on a Passenger-managed process.

Incremental by default (CLAUDE.md §2.3) — cheap to run often. Pass --full for a complete
re-pull (first run, suspected drift).

Usage: uv run python scripts/run_catalog_sync_once.py [--full]
"""

import argparse
import asyncio
import logging

from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.catalog.scheduler import run_catalog_sync
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.run_catalog_sync_once")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="ignore checkpoints, re-pull everything"
    )
    args = parser.parse_args()

    result = asyncio.run(run_catalog_sync(SessionLocal, settings, full=args.full))
    for entry in result.busy:
        logger.info(
            "sync: entity=%s changed=%d stored=%d failed=%d",
            entry.entity,
            entry.changed,
            entry.stored,
            entry.failed,
        )
    if result.woo is not None:
        logger.info(
            "sync: entity=woocommerce created=%d updated=%d skipped=%d failed=%d",
            result.woo.created,
            result.woo.updated,
            result.woo.skipped,
            result.woo.failed,
        )


if __name__ == "__main__":
    main()
