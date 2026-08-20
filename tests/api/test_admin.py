"""API-level: GET /api/v1/admin/users, /admin/quotations, /admin/sales-people — all
superadmin-only, all unscoped by branch."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Salesman, User
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
    salesman: Salesman,
) -> None:
    body = {
        "idempotency_key": "admin-view-1",
        "vch_no_prefix": "RCC",
        "date": "20-08-2026",
        "sale_type_name": "Repair",
        "customer_name": "Admin View Customer",
        "sales_person_id": salesman.busy_code,
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
    db_session: Session, superadmin_headers: dict[str, str], salesman: Salesman
) -> None:
    salesman.is_active = False
    db_session.commit()

    with TestClient(app) as client:
        # GET /api/v1/sales-people (caller-facing) hides inactive ones...
        assert client.get("/api/v1/sales-people").json() == []

        # ...but the admin view still shows them, so a superadmin can see who got blocked.
        admin_listed = client.get("/api/v1/admin/sales-people", headers=superadmin_headers)
        assert admin_listed.status_code == 200
        codes = {p["busy_code"]: p["is_active"] for p in admin_listed.json()}
        assert codes[salesman.busy_code] is False
