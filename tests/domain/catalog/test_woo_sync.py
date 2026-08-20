"""app/domain/catalog/woo_sync.py tests — Sprint 2 DoD:

  - "add a genuinely new item... run sync without the seed-import flag... does not
    appear in WooCommerce until the explicit opt-in is triggered" (seed mode)
  - "syncing two products in the same category creates exactly one WooCommerce
    category, not two" (dedup)

Runs against the mock WooCommerce server + real local MySQL (tests/conftest.py). The
DoD's other two items ask for a *live* test against real BUSY/WooCommerce sites — not
achievable in this environment (no live BUSY host is reachable here, see
docs/sprints/sprint-00-foundations.md), so those stay flagged, not silently claimed done.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Category, Product
from app.domain.catalog.woo_sync import (
    get_woo_sync_state,
    push_products_by_code,
    push_products_to_woocommerce,
    set_seeded,
)
from app.integrations.woocommerce import WooCommerceClient
from tests.fixtures.mock_woo import MockWooServer


def _add_product(db_session: Session, *, code: int, group: str, price: str) -> None:
    if db_session.get(Category, group) is None:
        db_session.add(Category(busy_group_name=group))
    db_session.add(
        Product(
            busy_code=code,
            name=f"Product {code}",
            price=Decimal(price),
            unit="Pcs.",
            item_group=group,
            tracks_stock=True,
            is_active=True,
        )
    )
    db_session.commit()


async def test_seed_mode_makes_zero_woocommerce_calls(
    db_session: Session, woo_client: WooCommerceClient, woo_server: MockWooServer
) -> None:
    _add_product(db_session, code=101, group="General", price="1000")
    _add_product(db_session, code=102, group="General", price="1200")

    result = await push_products_to_woocommerce(db_session, woo_client)

    assert (result.seeded, result.created, result.updated) == (2, 0, 0)
    assert woo_server.products == []
    assert woo_server.categories == []

    products = {p.busy_code: p for p in db_session.query(Product).all()}
    assert products[101].woo_product_id is None
    assert products[102].woo_product_id is None
    assert get_woo_sync_state(db_session).seeded is False


async def test_seed_import_creates_products_and_dedups_category(
    db_session: Session, woo_client: WooCommerceClient, woo_server: MockWooServer
) -> None:
    _add_product(db_session, code=101, group="General", price="1000")
    _add_product(db_session, code=102, group="General", price="1200")
    _add_product(db_session, code=103, group="Accessories", price="500")

    set_seeded(db_session)
    result = await push_products_to_woocommerce(db_session, woo_client)

    assert (result.seeded, result.created, result.failed) == (0, 3, 0)
    assert len(woo_server.products) == 3
    # Two products share "General" — exactly one category created for it, not two.
    assert len(woo_server.categories) == 2
    general_ids = {c["id"] for c in woo_server.categories if c["name"] == "General"}
    assert len(general_ids) == 1

    products = {p.busy_code: p for p in db_session.query(Product).all()}
    assert products[101].woo_product_id is not None
    assert products[102].woo_product_id is not None
    assert products[101].woo_synced_price == Decimal("1000")

    woo_products_by_sku = {p["sku"]: p for p in woo_server.products}
    assert woo_products_by_sku["101"]["categories"][0]["id"] in general_ids
    assert woo_products_by_sku["102"]["categories"][0]["id"] in general_ids
    assert woo_products_by_sku["101"]["status"] == "private"


async def test_price_change_updates_only_the_changed_product(
    db_session: Session, woo_client: WooCommerceClient, woo_server: MockWooServer
) -> None:
    _add_product(db_session, code=101, group="General", price="1000")
    _add_product(db_session, code=102, group="General", price="1200")
    set_seeded(db_session)
    first = await push_products_to_woocommerce(db_session, woo_client)
    assert first.created == 2

    # Nothing changed — second run must skip both, no WooCommerce calls for either.
    second = await push_products_to_woocommerce(db_session, woo_client)
    assert (second.created, second.updated, second.skipped) == (0, 0, 2)

    product_101 = db_session.get(Product, 101)
    assert product_101 is not None
    product_101.price = Decimal("1500")
    db_session.commit()

    third = await push_products_to_woocommerce(db_session, woo_client)
    assert (third.updated, third.skipped) == (1, 1)

    updated_woo_product = next(p for p in woo_server.products if p["sku"] == "101")
    assert Decimal(updated_woo_product["regular_price"]) == Decimal("1500")
    unchanged_woo_product = next(p for p in woo_server.products if p["sku"] == "102")
    assert Decimal(unchanged_woo_product["regular_price"]) == Decimal("1200")


async def test_push_products_by_code_bypasses_seed_mode(
    db_session: Session, woo_client: WooCommerceClient, woo_server: MockWooServer
) -> None:
    """Unlike push_products_to_woocommerce, an explicit hand-picked push must create the
    product even while seed mode is still on — picking it IS the opt-in."""
    _add_product(db_session, code=101, group="General", price="1000")
    _add_product(db_session, code=102, group="General", price="1200")
    assert get_woo_sync_state(db_session).seeded is False

    results = await push_products_by_code(db_session, woo_client, [101])

    assert len(results) == 1
    assert results[0].action == "created"
    assert len(woo_server.products) == 1
    product_101 = db_session.get(Product, 101)
    assert product_101 is not None
    assert product_101.woo_product_id is not None
    # The other product was never mentioned — still untouched, still in seed mode.
    product_102 = db_session.get(Product, 102)
    assert product_102 is not None
    assert product_102.woo_product_id is None


async def test_push_products_by_code_updates_price_and_skips_unchanged(
    db_session: Session, woo_client: WooCommerceClient, woo_server: MockWooServer
) -> None:
    _add_product(db_session, code=101, group="General", price="1000")
    await push_products_by_code(db_session, woo_client, [101])

    unchanged = await push_products_by_code(db_session, woo_client, [101])
    assert unchanged[0].action == "skipped"

    product_101 = db_session.get(Product, 101)
    assert product_101 is not None
    product_101.price = Decimal("1500")
    db_session.commit()

    updated = await push_products_by_code(db_session, woo_client, [101])
    assert updated[0].action == "updated"
    woo_product = next(p for p in woo_server.products if p["sku"] == "101")
    assert Decimal(woo_product["regular_price"]) == Decimal("1500")


async def test_push_products_by_code_reports_unknown_product(
    db_session: Session, woo_client: WooCommerceClient
) -> None:
    results = await push_products_by_code(db_session, woo_client, [999999])
    assert len(results) == 1
    assert results[0].busy_code == 999999
    assert results[0].action == "not_found"
