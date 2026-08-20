"""app/domain/catalog/queries.py's set_product_barcode (local-only field, survives
catalog re-syncs — CLAUDE.md §8: no real barcode data exists in BUSY for this company) and
list_salesmen/get_salesman (BUSY's Executive master, synced read-only)."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import Category, Product, Salesman
from app.domain.catalog.queries import (
    DuplicateBarcodeError,
    ProductNotFoundError,
    get_salesman,
    list_salesmen,
    set_product_barcode,
)

UNCATEGORISED = "Uncategorised"


def _make_product(session: Session, code: int, name: str) -> Product:
    session.merge(Category(busy_group_name=UNCATEGORISED))
    product = Product(
        busy_code=code, name=name, price=Decimal("100"), unit="Pcs.", item_group=UNCATEGORISED
    )
    session.add(product)
    session.commit()
    return product


def test_set_product_barcode_assigns_it(db_session: Session) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")

    product = set_product_barcode(db_session, 1613, "1234567890")

    assert product.barcode == "1234567890"


def test_set_product_barcode_rejects_unknown_product(db_session: Session) -> None:
    with pytest.raises(ProductNotFoundError):
        set_product_barcode(db_session, 999999, "1234567890")


def test_set_product_barcode_rejects_duplicate_across_products(db_session: Session) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")
    _make_product(db_session, 1614, "Cable-infinix Typ C")
    set_product_barcode(db_session, 1613, "1234567890")

    with pytest.raises(DuplicateBarcodeError):
        set_product_barcode(db_session, 1614, "1234567890")


def test_set_product_barcode_allows_reassigning_same_product(db_session: Session) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")
    set_product_barcode(db_session, 1613, "1234567890")

    product = set_product_barcode(db_session, 1613, "9999999999")

    assert product.barcode == "9999999999"


def test_list_salesmen_excludes_inactive_by_default(db_session: Session) -> None:
    db_session.add_all(
        [
            Salesman(busy_code=401, name="Femi Sales", is_active=True),
            Salesman(busy_code=402, name="Blocked Sales", is_active=False),
        ]
    )
    db_session.commit()

    assert [s.name for s in list_salesmen(db_session)] == ["Femi Sales"]
    assert {s.name for s in list_salesmen(db_session, active_only=False)} == {
        "Femi Sales",
        "Blocked Sales",
    }


def test_get_salesman_returns_none_for_unknown_code(db_session: Session) -> None:
    assert get_salesman(db_session, 999999) is None
