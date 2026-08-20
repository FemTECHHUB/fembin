"""API-level: GET /api/v1/admin/users, /admin/quotations, /admin/sales-people,
PATCH /api/v1/admin/sales-people/{id} — all superadmin-only, all unscoped by branch."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter, SalesPerson, User
from app.domain.orders.sales_people import create_sales_person
from app.main import app


def test_admin_routes_require_superadmin(db_session: Session, auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/users", headers=auth_headers).status_code == 403
        assert client.get("/api/v1/admin/quotations", headers=auth_headers).status_code == 403
        assert client.get("/api/v1/admin/sales-people", headers=auth_headers).status_code == 403


def test_admin_routes_require_authentication(db_session: Session) -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/users").status_code == 401


def test_admin_list_users_shows_every_branch(
    db_session: Session, superadmin_headers: dict[str, str], test_user: User
) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/users", headers=superadmin_headers)
        assert resp.status_code == 200
        usernames = {u["username"] for u in resp.json()}
        assert test_user.username in usernames
        assert "root.admin" in usernames  # the superadmin itself


def test_admin_list_quotations_is_unscoped(
    db_session: Session,
    superadmin_headers: dict[str, str],
    auth_headers: dict[str, str],
    sales_person: SalesPerson,
) -> None:
    body = {
        "idempotency_key": "admin-view-1",
        "vch_no_prefix": "RCC",
        "date": "20-08-2026",
        "sale_type_name": "Repair",
        "customer_name": "Admin View Customer",
        "sales_person_id": sales_person.id,
        "items": [
            {
                "item_name": "Acer Laptop",
                "unit_name": "Pcs.",
                "qty": "1",
                "price": "1",
                "amount": "1",
            }
        ],
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/quotations", json=body, headers=auth_headers)
        assert created.status_code == 202

        admin_list = client.get("/api/v1/admin/quotations", headers=superadmin_headers)
        assert admin_list.status_code == 200
        assert created.json()["id"] in [j["id"] for j in admin_list.json()]


def test_admin_list_sales_people_includes_inactive(
    db_session: Session, superadmin_headers: dict[str, str], material_center: MaterialCenter
) -> None:
    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )
    with TestClient(app) as client:
        deactivate = client.patch(
            f"/api/v1/admin/sales-people/{person.id}",
            headers=superadmin_headers,
            json={"is_active": False},
        )
        assert deactivate.status_code == 200
        assert deactivate.json()["is_active"] is False

        listed = client.get("/api/v1/admin/sales-people", headers=superadmin_headers)
        assert person.id in [p["id"] for p in listed.json()]


def test_admin_reassign_sales_person_branch(
    db_session: Session, superadmin_headers: dict[str, str], material_center: MaterialCenter
) -> None:
    other_center = MaterialCenter(busy_code=1155, name="Repair Centre Taiwo", is_active=True)
    db_session.add(other_center)
    db_session.commit()

    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )
    with TestClient(app) as client:
        resp = client.patch(
            f"/api/v1/admin/sales-people/{person.id}",
            headers=superadmin_headers,
            json={"material_center_code": 1155},
        )
        assert resp.status_code == 200
        assert resp.json()["material_center_code"] == 1155
