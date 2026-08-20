"""API-level: GET/POST /api/v1/sales-people."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter, SalesPerson
from app.main import app


def test_list_sales_people_requires_authentication(db_session: Session) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/sales-people")
        assert resp.status_code == 401


def test_list_sales_people_scoped_to_caller_material_center(
    db_session: Session, auth_headers: dict[str, str], sales_person: SalesPerson
) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/sales-people", headers=auth_headers)
        assert resp.status_code == 200
        names = [p["full_name"] for p in resp.json()]
        assert names == [sales_person.full_name]


def test_create_sales_person_requires_superadmin(
    db_session: Session, auth_headers: dict[str, str], material_center: MaterialCenter
) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/sales-people",
            headers=auth_headers,
            json={"full_name": "Femi Sales", "material_center_code": material_center.busy_code},
        )
        assert resp.status_code == 403


def test_create_sales_person_as_superadmin(
    db_session: Session, superadmin_headers: dict[str, str], material_center: MaterialCenter
) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/sales-people",
            headers=superadmin_headers,
            json={"full_name": "Femi Sales", "material_center_code": material_center.busy_code},
        )
        assert resp.status_code == 201
        assert resp.json()["material_center_code"] == material_center.busy_code
