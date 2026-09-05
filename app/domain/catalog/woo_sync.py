"""BUSY -> WooCommerce push: existing products update live immediately; brand-new items
are created as `private` (configurable) for manual review; deactivated BUSY items are
set to `private` on the store (CLAUDE.md §2.4 — marks inactive, never deletes) and
re-published if BUSY ever reactivates them. Ported from the prototype's
`syncService.js`, redesigned around our MySQL mirror instead of a JSON state file — the
`products`/`categories` tables already carry everything this needs (`woo_product_id`,
`woo_synced_price`, `woo_synced_name`, `woo_hidden`, `categories.woo_category_id`), so
there's no separate state file to keep in sync with them.

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
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Category, Product, WooSyncState
from app.integrations.woocommerce import WooCommerceClient, WooCommerceError

logger = logging.getLogger(__name__)

_HIDDEN_STATUS = "private"  # off-sale: a BUSY-deactivated product on WooCommerce
_PUBLISHED_STATUS = "publish"  # back on sale: BUSY reactivated, or our own hidden product


def _create_payload(product: Product, category_id: int, status: str) -> dict[str, Any]:
    """WooCommerce create body for a never-pushed product."""
    return {
        "name": product.name,
        "sku": str(product.busy_code),
        "regular_price": str(product.price),
        "manage_stock": False,
        "status": status,
        "categories": [{"id": category_id}],
    }


def _sync_payload(
    product: Product, category_id: int, *, status: str | None = None
) -> dict[str, Any]:
    """WooCommerce update body — keeps whatever status the store owner set unless we are
    deliberately hiding (`_HIDDEN_STATUS`) or re-publishing (`_PUBLISHED_STATUS`) it."""
    payload: dict[str, Any] = {
        "name": product.name,
        "regular_price": str(product.price),
        "categories": [{"id": category_id}],
    }
    if status is not None:
        payload["status"] = status
    return payload


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
    WooCommerce push: never-pushed active products (`woo_product_id IS NULL`), already
    pushed ones whose BUSY price or name has since changed, and previously pushed products
    whose BUSY record has been deactivated (hidden) or reactivated (re-published). Stock
    is deliberately not pushed (PRD §5 non-goal, unsolved — see CLAUDE.md §8).

    Handles the hidden/revealed lifecycle in both directions without re-issuing the same
    status update every pass (`woo_hidden` is set once the `private` PUT has landed, and
    cleared once BUSY reactivates it — CLAUDE.md §2.4, no DELETE)."""
    state = get_woo_sync_state(session)
    seed_mode = not state.seeded

    products = session.scalars(
        select(Product).where(or_(Product.is_active.is_(True), Product.woo_product_id.isnot(None)))
    ).all()

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
                    _create_payload(product, category_id, new_product_status)
                )
                product.woo_product_id = int(created_product["id"])
                product.woo_synced_price = product.price
                product.woo_synced_name = product.name
                product.woo_hidden = False
                created += 1
            except (WooCommerceError, httpx.HTTPError) as exc:
                logger.warning(
                    "WooCommerce create failed for product %s: %s", product.busy_code, exc
                )
                failed += 1
            continue

        if not product.is_active:
            if product.woo_hidden:
                skipped += 1
                continue
            try:
                await woo.update_product(product.woo_product_id, {"status": _HIDDEN_STATUS})
                product.woo_hidden = True
                updated += 1
            except (WooCommerceError, httpx.HTTPError) as exc:
                logger.warning("WooCommerce hide failed for product %s: %s", product.busy_code, exc)
                failed += 1
            continue

        if product.woo_hidden:
            # BUSY reactivated it — bring it back on the store.
            try:
                category_id = await _ensure_category(session, woo, product.item_group)
                await woo.update_product(
                    product.woo_product_id,
                    _sync_payload(product, category_id, status=_PUBLISHED_STATUS),
                )
                product.woo_hidden = False
                product.woo_synced_price = product.price
                product.woo_synced_name = product.name
                updated += 1
            except (WooCommerceError, httpx.HTTPError) as exc:
                logger.warning(
                    "WooCommerce republish failed for product %s: %s", product.busy_code, exc
                )
                failed += 1
            continue

        if product.woo_synced_price == product.price and product.woo_synced_name == product.name:
            skipped += 1
            continue

        try:
            category_id = await _ensure_category(session, woo, product.item_group)
            await woo.update_product(product.woo_product_id, _sync_payload(product, category_id))
            product.woo_synced_price = product.price
            product.woo_synced_name = product.name
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
        if product is None:
            results.append(WooPushItemResult(busy_code=code, name="", action="not_found"))
            continue
        if not product.is_active:
            # Deactivated in BUSY (CLAUDE.md §2.4) — never push a discontinued item live,
            # and don't mislabel it as "not_found": it exists, it's just deactivated.
            results.append(WooPushItemResult(busy_code=code, name=product.name, action="skipped"))
            continue

        try:
            if product.woo_product_id is None:
                category_id = await _ensure_category(session, woo, product.item_group)
                created_product = await woo.create_product(
                    _create_payload(product, category_id, new_product_status)
                )
                product.woo_product_id = int(created_product["id"])
                product.woo_synced_price = product.price
                product.woo_synced_name = product.name
                product.woo_hidden = False
                session.commit()
                results.append(
                    WooPushItemResult(busy_code=code, name=product.name, action="created")
                )
                continue

            if (
                not product.woo_hidden
                and product.woo_synced_price == product.price
                and product.woo_synced_name == product.name
            ):
                results.append(
                    WooPushItemResult(busy_code=code, name=product.name, action="skipped")
                )
                continue

            category_id = await _ensure_category(session, woo, product.item_group)
            await woo.update_product(
                product.woo_product_id,
                _sync_payload(
                    product,
                    category_id,
                    status=_PUBLISHED_STATUS if product.woo_hidden else None,
                ),
            )
            product.woo_hidden = False
            product.woo_synced_price = product.price
            product.woo_synced_name = product.name
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
