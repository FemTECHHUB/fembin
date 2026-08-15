"""Catalog API tests. Sprint 1 DoD: "No endpoint in this sprint ever calls BUSY
synchronously inside a request — all BUSY calls happen in the scheduled sync job; API
endpoints only ever read MySQL." The trigger test proves this structurally: the route
hands the job to BackgroundTasks rather than awaiting it, so the response can return
before any BUSY call happens.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.schemas import SyncRequest
from app.api.v1.sync import trigger_products_sync
from app.config import get_settings
from app.db.models import Category, MaterialCenter, Product
from app.domain.catalog.scheduler import run_catalog_sync
from app.main import app


class _FakeBackgroundTasks:
    def __init__(self) -> None:
        self.added: list[
            tuple[Callable[..., Coroutine[Any, Any, Any]], tuple[Any, ...], dict[str, Any]]
        ] = []

    def add_task(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
    ) -> None:
        self.added.append((func, args, kwargs))


def test_trigger_products_sync_hands_off_to_background_tasks_not_inline() -> None:
    background_tasks = _FakeBackgroundTasks()

    result = trigger_products_sync(
        SyncRequest(full=True),
        background_tasks,  # type: ignore[arg-type]
        settings=get_settings(),
    )

    assert result.status == "scheduled"
    assert len(background_tasks.added) == 1
    func, _args, kwargs = background_tasks.added[0]
    assert func is run_catalog_sync
    assert kwargs == {"full": True}


def test_products_categories_material_centers_and_sync_status_routes(db_session: Session) -> None:
    db_session.add(Category(busy_group_name="General"))
    db_session.add(
        Product(
            busy_code=901,
            name="Test Widget",
            price=1500,
            unit="Pcs.",
            item_group="General",
            tracks_stock=True,
            is_active=True,
        )
    )
    db_session.add(MaterialCenter(busy_code=701, name="Test Branch", is_active=True))
    db_session.commit()

    with TestClient(app) as client:
        products_resp = client.get("/api/v1/products")
        assert products_resp.status_code == 200
        assert any(p["busy_code"] == 901 for p in products_resp.json())

        product_resp = client.get("/api/v1/products/901")
        assert product_resp.status_code == 200
        assert product_resp.json()["name"] == "Test Widget"

        missing_resp = client.get("/api/v1/products/999999")
        assert missing_resp.status_code == 404

        categories_resp = client.get("/api/v1/categories")
        assert categories_resp.status_code == 200
        assert any(c["busy_group_name"] == "General" for c in categories_resp.json())

        material_centers_resp = client.get("/api/v1/material-centers")
        assert material_centers_resp.status_code == 200
        assert any(mc["busy_code"] == 701 for mc in material_centers_resp.json())

        status_resp = client.get("/api/v1/sync/status")
        assert status_resp.status_code == 200
