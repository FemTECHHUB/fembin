"""API-level: POST /api/v1/quotations enqueues without ever touching BUSY inline (it's a
local DB insert only — app/domain/orders/quotations.py), and GET /api/v1/outbox/{id} lets
a caller check what happened to it."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def _quotation_body(idempotency_key: str) -> dict[str, object]:
    return {
        "idempotency_key": idempotency_key,
        "vch_no_prefix": "RCC",
        "date": "15-08-2026",
        "sale_type_name": "Repair",
        "customer_name": "Amit Gupta",
        "material_center_name": "Main Store",
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


def test_create_sale_quotation_and_fetch_outbox_status(db_session: Session) -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/v1/quotations", json=_quotation_body("api-quote-1"))
        assert create_resp.status_code == 202
        body = create_resp.json()
        assert body["status"] == "queued"
        job_id = body["id"]

        status_resp = client.get(f"/api/v1/outbox/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == job_id

        missing_resp = client.get("/api/v1/outbox/999999")
        assert missing_resp.status_code == 404


def test_create_sale_quotation_is_idempotent(db_session: Session) -> None:
    with TestClient(app) as client:
        first = client.post("/api/v1/quotations", json=_quotation_body("api-quote-dup"))
        second = client.post("/api/v1/quotations", json=_quotation_body("api-quote-dup"))
        assert first.json()["id"] == second.json()["id"]


def test_list_sale_quotations_shows_status(db_session: Session) -> None:
    with TestClient(app) as client:
        first = client.post("/api/v1/quotations", json=_quotation_body("api-list-1"))
        second = client.post("/api/v1/quotations", json=_quotation_body("api-list-2"))

        list_resp = client.get("/api/v1/quotations")
        assert list_resp.status_code == 200
        jobs = list_resp.json()
        ids = [j["id"] for j in jobs]
        assert first.json()["id"] in ids
        assert second.json()["id"] in ids
        assert all(j["status"] == "queued" for j in jobs)
