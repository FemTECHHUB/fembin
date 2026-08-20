"""BUSY -> WooCommerce push: existing products update live immediately; brand-new items
are created as `private` (configurable) for manual review. Ported from the prototype's
`syncService.js`, redesigned around our MySQL mirror instead of a JSON state file — the
`products`/`categories` tables (Sprint 1) already carry everything this needs
(`woo_product_id`, `woo_synced_price`, `categories.woo_category_id`), so there's no
separate state file to keep in sync with them.

FIRST-RUN SAFETY NET (ported faithfully — CLAUDE.md: understand why it's shaped the way
it is, don't simplify away). The first time this runs, most/all active products look
"new" (never pushed). Rather than silently bulk-creating the whole catalog in WooCommerce,
it stays in SEED MODE — zero WooCommerce calls — until `set_seeded()` is called once,
explicitly (see scripts/seed_import_woocommerce.py). That's a permanent, one-time opt-in;
after that, every genuinely new item is created automatically, forever.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category, Product, WooSyncState
from app.integrations.woocommerce import WooCommerceClient, WooCommerceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WooPushResult:
    seeded: int
    created: int
    updated: int
    skipped: int
    failed: int


@dataclass(frozen=True)
class WooPushItemResult:
    busy_code: int
    name: str
    action: str  # "created" | "updated" | "skipped" | "failed" | "not_found"
    error: str | None = None


def get_woo_sync_state(session: Session) -> WooSyncState:
    state = session.get(WooSyncState, 1)
    if state is None:
        state = WooSyncState(id=1)
        session.add(state)
        session.flush()
    return state


def set_seeded(session: Session) -> None:
    """Permanent, one-time opt-in: from now on, genuinely new items are created in
    WooCommerce automatically. Idempotent — calling it again is a no-op."""
    state = get_woo_sync_state(session)
    state.seeded = True
    session.commit()


async def _ensure_category(session: Session, woo: WooCommerceClient, group_name: str) -> int:
    """Create the WooCommerce category once, then reuse it — never create a duplicate for
    the same group name (verified behavior in the prototype, don't regress it)."""
    category = session.get(Category, group_name)
    if category is not None and category.woo_category_id is not None:
        return category.woo_category_id

    existing = await woo.find_category_by_name(group_name)
    woo_category_id = existing["id"] if existing else (await woo.create_category(group_name))["id"]

    if category is None:
        category = Category(busy_group_name=group_name, woo_category_id=woo_category_id)
        session.add(category)
    else:
        category.woo_category_id = woo_category_id
    session.flush()
    return int(woo_category_id)


async def push_products_to_woocommerce(
    session: Session, woo: WooCommerceClient, *, new_product_status: str = "private"
) -> WooPushResult:
    """Scans the local `products` mirror (not a fresh BUSY pull) for rows needing a
    WooCommerce push: never-pushed active products (`woo_product_id IS NULL`) and
    already-pushed ones whose BUSY price has since changed. Stock is deliberately not
    pushed (PRD §5 non-goal, unsolved — see CLAUDE.md §8)."""
    state = get_woo_sync_state(session)
    seed_mode = not state.seeded

    products = session.scalars(select(Product).where(Product.is_active)).all()

    seeded = created = updated = skipped = failed = 0
    for product in products:
        if product.woo_product_id is None:
            if seed_mode:
                # Already recorded by Sprint 1's BUSY sync (the row itself is the
                # record) — deliberately zero WooCommerce calls until set_seeded().
                seeded += 1
                continue
            try:
                category_id = await _ensure_category(session, woo, product.item_group)
                created_product = await woo.create_product(
                    {
                        "name": product.name,
                        "sku": str(product.busy_code),
                        "regular_price": str(product.price),
                        "manage_stock": False,
                        "status": new_product_status,
                        "categories": [{"id": category_id}],
                    }
                )
                product.woo_product_id = int(created_product["id"])
                product.woo_synced_price = product.price
                created += 1
            except (WooCommerceError, httpx.HTTPError) as exc:
                logger.warning(
                    "WooCommerce create failed for product %s: %s", product.busy_code, exc
                )
                failed += 1
            continue

        if product.woo_synced_price == product.price:
            skipped += 1
            continue

        try:
            await woo.update_product(product.woo_product_id, {"regular_price": str(product.price)})
            product.woo_synced_price = product.price
            updated += 1
        except (WooCommerceError, httpx.HTTPError) as exc:
            logger.warning("WooCommerce update failed for product %s: %s", product.busy_code, exc)
            failed += 1

    state.last_run_at = datetime.now(UTC).replace(tzinfo=None)
    state.last_seeded = seeded
    state.last_created = created
    state.last_updated = updated
    state.last_skipped = skipped
    state.last_failed = failed
    session.commit()

    return WooPushResult(
        seeded=seeded, created=created, updated=updated, skipped=skipped, failed=failed
    )


async def push_products_by_code(
    session: Session,
    woo: WooCommerceClient,
    busy_codes: list[int],
    *,
    new_product_status: str = "private",
) -> list[WooPushItemResult]:
    """Push specifically chosen products now — a superadmin clicking "push these to the
    website" (app/api/v1/sync.py), not the periodic full-catalog pass above.

    Deliberately bypasses seed mode: the whole point of seed mode is to stop an
    *automatic* sync from silently bulk-creating a live site's worth of products.
    Someone hand-picking specific products and clicking a button is already the explicit,
    one-at-a-time opt-in seed mode exists to wait for — gating it again here would just
    make the button not work until a separate seed-import was also run."""
    results: list[WooPushItemResult] = []
    for code in busy_codes:
        product = session.get(Product, code)
        if product is None or not product.is_active:
            results.append(WooPushItemResult(busy_code=code, name="", action="not_found"))
            continue

        try:
            if product.woo_product_id is None:
                category_id = await _ensure_category(session, woo, product.item_group)
                created_product = await woo.create_product(
                    {
                        "name": product.name,
                        "sku": str(product.busy_code),
                        "regular_price": str(product.price),
                        "manage_stock": False,
                        "status": new_product_status,
                        "categories": [{"id": category_id}],
                    }
                )
                product.woo_product_id = int(created_product["id"])
                product.woo_synced_price = product.price
                session.commit()
                results.append(
                    WooPushItemResult(busy_code=code, name=product.name, action="created")
                )
                continue

            if product.woo_synced_price == product.price:
                results.append(
                    WooPushItemResult(busy_code=code, name=product.name, action="skipped")
                )
                continue

            await woo.update_product(product.woo_product_id, {"regular_price": str(product.price)})
            product.woo_synced_price = product.price
            session.commit()
            results.append(WooPushItemResult(busy_code=code, name=product.name, action="updated"))
        except (WooCommerceError, httpx.HTTPError) as exc:
            session.rollback()
            logger.warning("Manual WooCommerce push failed for product %s: %s", code, exc)
            results.append(
                WooPushItemResult(
                    busy_code=code, name=product.name, action="failed", error=str(exc)
                )
            )

    return results
