"""API-level: PUT /api/v1/products/{code}/barcode — superadmin-only, local field."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Category, Product
from app.main import app

UNCATEGORISED = "Uncategorised"


def _make_product(session: Session, code: int, name: str) -> Product:
    session.merge(Category(busy_group_name=UNCATEGORISED))
    product = Product(
        busy_code=code, name=name, price=Decimal("100"), unit="Pcs.", item_group=UNCATEGORISED
    )
    session.add(product)
    session.commit()
    return product


def test_set_product_barcode_requires_superadmin(
    db_session: Session, auth_headers: dict[str, str]
) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")
    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/products/1613/barcode", headers=auth_headers, json={"barcode": "1234567890"}
        )
        assert resp.status_code == 403


def test_set_product_barcode_as_superadmin(
    db_session: Session, superadmin_headers: dict[str, str]
) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")
    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/products/1613/barcode",
            headers=superadmin_headers,
            json={"barcode": "1234567890"},
        )
        assert resp.status_code == 200
        assert resp.json()["barcode"] == "1234567890"

        listed = client.get("/api/v1/products").json()
        assert next(p for p in listed if p["busy_code"] == 1613)["barcode"] == "1234567890"


def test_set_product_barcode_rejects_duplicate(
    db_session: Session, superadmin_headers: dict[str, str]
) -> None:
    _make_product(db_session, 1613, "Cable-infinix Micro")
    _make_product(db_session, 1614, "Cable-infinix Typ C")
    with TestClient(app) as client:
        first = client.put(
            "/api/v1/products/1613/barcode",
            headers=superadmin_headers,
            json={"barcode": "1234567890"},
        )
        assert first.status_code == 200

        conflict = client.put(
            "/api/v1/products/1614/barcode",
            headers=superadmin_headers,
            json={"barcode": "1234567890"},
        )
        assert conflict.status_code == 409


def test_set_product_barcode_unknown_product(
    db_session: Session, superadmin_headers: dict[str, str]
) -> None:
    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/products/999999/barcode",
            headers=superadmin_headers,
            json={"barcode": "1234567890"},
        )
        assert resp.status_code == 404
