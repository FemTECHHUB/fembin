#!/usr/bin/env python3
"""One-time, explicit opt-in to push the existing product backlog live to WooCommerce.

Sprint 2's seed-mode safety net (app/domain/catalog/woo_sync.py): the first time the
catalog sync runs, every active product looks "new" to WooCommerce. Rather than silently
bulk-creating the whole catalog, the sync stays in seed mode — zero WooCommerce calls —
until this script is run once, deliberately.

Kept as a CLI script rather than an HTTP endpoint: there's no auth system in this
codebase yet (see docs/sprints/sprint-01-busy-read-layer.md), and "bulk-create N live
products" should not be one unauthenticated HTTP call away.

Usage: uv run python scripts/seed_import_woocommerce.py
"""

import asyncio

from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.catalog.woo_sync import (
    get_woo_sync_state,
    push_products_to_woocommerce,
    set_seeded,
)
from app.integrations.woocommerce import WooCommerceClient


async def main() -> None:
    settings = get_settings()
    if not settings.woo_site_url:
        raise SystemExit("WOO_SITE_URL is not configured — nothing to seed-import into.")

    session = SessionLocal()
    try:
        state = get_woo_sync_state(session)
        if state.seeded:
            print("Already seeded — this is a one-time, permanent opt-in. Nothing to do.")
            return

        confirm = input(
            "This will push the ENTIRE current product backlog live to WooCommerce "
            f"(as '{settings.woo_new_product_status}'). This cannot be undone. "
            "Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

        set_seeded(session)
        async with WooCommerceClient.from_settings(settings) as woo:
            result = await push_products_to_woocommerce(
                session, woo, new_product_status=settings.woo_new_product_status
            )
        print(
            f"Seed import done: created={result.created} updated={result.updated} "
            f"skipped={result.skipped} failed={result.failed}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
