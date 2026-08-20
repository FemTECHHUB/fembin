"""API-level: POST /api/v1/quotations enqueues without ever touching BUSY inline (it's a
local DB insert only — app/domain/orders/quotations.py), and GET /api/v1/outbox/{id} lets
a caller check what happened to it.

Every route requires an authenticated user (auth_headers fixture, tests/conftest.py) — the
quotation's material center always comes from that user's own assignment, never the
request body (CLAUDE.md NFR6). sales_person_id must match a real, active salesman synced
from BUSY's Executive master (app/db/models.py's `Salesman`)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MaterialCenter, Salesman
from app.domain.auth.tokens import create_access_token
from app.domain.auth.users import create_user
from app.main import app


def _quotation_body(idempotency_key: str, *, sales_person_id: int) -> dict[str, object]:
    return {
        "idempotency_key": idempotency_key,
        "vch_no_prefix": "RCC",
        "date": "15-08-2026",
        "sale_type_name": "Repair",
        "customer_name": "Amit Gupta",
        "sales_person_id": sales_person_id,
        "items": [
            {
                "item_name": "Acer Laptop",
                "unit_name": "Pcs.",
                "qty": "1",
                "price": "26000",
                "amount": "26000",
            }
        ],
    }


def test_quotations_require_authentication(db_session: Session) -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/quotations", json=_quotation_body("api-noauth", sales_person_id=1)
        )
        assert create_resp.status_code == 401  # no Authorization header at all

        list_resp = client.get("/api/v1/quotations")
        assert list_resp.status_code == 401


def test_create_sale_quotation_and_fetch_outbox_status(
    db_session: Session, auth_headers: dict[str, str], salesman: Salesman
) -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-quote-1", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        assert create_resp.status_code == 202
        body = create_resp.json()
        assert body["status"] == "queued"
        assert body["payload"]["sales_person_name"] == salesman.name
        job_id = body["id"]

        status_resp = client.get(f"/api/v1/outbox/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == job_id

        missing_resp = client.get("/api/v1/outbox/999999")
        assert missing_resp.status_code == 404


def test_create_sale_quotation_rejects_unknown_sales_person(
    db_session: Session, auth_headers: dict[str, str], material_center: MaterialCenter
) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-unknown-sp", sales_person_id=999999),
            headers=auth_headers,
        )
        assert resp.status_code == 422


def test_create_sale_quotation_rejects_inactive_sales_person(
    db_session: Session, auth_headers: dict[str, str], salesman: Salesman
) -> None:
    salesman.is_active = False
    db_session.commit()

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-inactive-sp", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        assert resp.status_code == 422


def test_create_sale_quotation_is_idempotent(
    db_session: Session, auth_headers: dict[str, str], salesman: Salesman
) -> None:
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-quote-dup", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        second = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-quote-dup", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        assert first.json()["id"] == second.json()["id"]


def test_list_sale_quotations_shows_status(
    db_session: Session, auth_headers: dict[str, str], salesman: Salesman
) -> None:
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-list-1", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        second = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-list-2", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )

        list_resp = client.get("/api/v1/quotations", headers=auth_headers)
        assert list_resp.status_code == 200
        jobs = list_resp.json()
        ids = [j["id"] for j in jobs]
        assert first.json()["id"] in ids
        assert second.json()["id"] in ids
        assert all(j["status"] == "queued" for j in jobs)


def test_list_sale_quotations_is_scoped_to_the_caller_material_center(
    db_session: Session, auth_headers: dict[str, str], salesman: Salesman
) -> None:
    """A second user tied to a different branch must never see the first user's
    quotations — proves the material-center tie is enforced, not just recorded."""
    other_center = MaterialCenter(busy_code=1155, name="Repair Centre Taiwo", is_active=True)
    db_session.add(other_center)
    db_session.commit()

    other_user = create_user(
        db_session,
        username="jane.cashier",
        password="test-pass-456",
        full_name="Jane Doe",
        material_center_code=other_center.busy_code,
    )
    other_headers = {
        "Authorization": f"Bearer {create_access_token(other_user, settings=get_settings())}"
    }

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/quotations",
            json=_quotation_body("api-scope-1", sales_person_id=salesman.busy_code),
            headers=auth_headers,
        )
        assert created.status_code == 202

        own_list = client.get("/api/v1/quotations", headers=auth_headers).json()
        other_list = client.get("/api/v1/quotations", headers=other_headers).json()

        assert created.json()["id"] in [j["id"] for j in own_list]
        assert created.json()["id"] not in [j["id"] for j in other_list]
