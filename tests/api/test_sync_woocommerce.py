"""API-level: POST /api/v1/sync/woocommerce/push — superadmin-only, immediate (not
BackgroundTasks, unlike /sync/products) since a "push these now" button needs a per-product
result to show. Calls the route function directly for the success path (same pattern as
test_catalog_routes.py's trigger test) so a custom Settings pointing at the mock
WooCommerce server can be passed without wiring FastAPI dependency_overrides."""

from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.schemas import WooPushRequest
from app.api.v1.sync import push_to_woocommerce_route
from app.config import Settings
from app.db.models import Category, Product, User
from app.main import app


def _add_product(db_session: Session, *, code: int, price: str = "1000") -> None:
    db_session.merge(Category(busy_group_name="General"))
    db_session.add(
        Product(
            busy_code=code,
            name=f"Product {code}",
            price=Decimal(price),
            unit="Pcs.",
            item_group="General",
            tracks_stock=True,
            is_active=True,
        )
    )
    db_session.commit()


def _fake_superadmin() -> User:
    return User(
        id=1,
        username="admin",
        password_hash="x",
        full_name="Admin",
        material_center_code=201,
        is_superadmin=True,
    )


async def test_push_to_woocommerce_route_creates_selected_product(
    db_session: Session, catalog_sync_settings: Settings
) -> None:
    _add_product(db_session, code=101)

    response = await push_to_woocommerce_route(
        WooPushRequest(busy_codes=[101]),
        db_session,
        catalog_sync_settings,
        _fake_superadmin(),
    )

    assert len(response.results) == 1
    assert response.results[0].action == "created"

    product = db_session.get(Product, 101)
    assert product is not None
    assert product.woo_product_id is not None


async def test_push_to_woocommerce_route_bypasses_seed_mode(
    db_session: Session, catalog_sync_settings: Settings
) -> None:
    """No set_seeded() call here — proves the manual push works on a fresh environment,
    unlike the periodic full-catalog sync."""
    _add_product(db_session, code=202)

    response = await push_to_woocommerce_route(
        WooPushRequest(busy_codes=[202]), db_session, catalog_sync_settings, _fake_superadmin()
    )

    assert response.results[0].action == "created"


async def test_push_to_woocommerce_route_requires_configured_woocommerce(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await push_to_woocommerce_route(
            WooPushRequest(busy_codes=[101]), db_session, Settings(), _fake_superadmin()
        )
    assert exc_info.value.status_code == 409


def test_push_to_woocommerce_route_requires_superadmin(
    db_session: Session, auth_headers: dict[str, str]
) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/sync/woocommerce/push",
            headers=auth_headers,
            json={"busy_codes": [101]},
        )
        assert resp.status_code == 403


def test_push_to_woocommerce_route_requires_authentication(db_session: Session) -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/sync/woocommerce/push", json={"busy_codes": [101]})
        assert resp.status_code == 401
