"""API-level: GET /api/v1/sales-people — read-only, synced from BUSY's Executive master
(MasterType=33), same pattern as /api/v1/products and /api/v1/material-centers."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Salesman
from app.main import app


def test_list_sales_people_returns_active_synced_salesmen(
    db_session: Session, salesman: Salesman
) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/sales-people")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert names == [salesman.name]


def test_list_sales_people_excludes_inactive(db_session: Session, salesman: Salesman) -> None:
    salesman.is_active = False
    db_session.commit()

    with TestClient(app) as client:
        resp = client.get("/api/v1/sales-people")
        assert resp.json() == []
