"""API-level: POST /api/v1/auth/users, POST /api/v1/auth/login."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter, User
from app.main import app


def test_create_user_and_login(db_session: Session, material_center: MaterialCenter) -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/auth/users",
            json={
                "username": "new.rep",
                "password": "a-real-password",
                "full_name": "New Rep",
                "material_center_code": material_center.busy_code,
            },
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["material_center_code"] == material_center.busy_code

        login_resp = client.post(
            "/api/v1/auth/login", json={"username": "new.rep", "password": "a-real-password"}
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["access_token"]

        bad_login = client.post(
            "/api/v1/auth/login", json={"username": "new.rep", "password": "wrong"}
        )
        assert bad_login.status_code == 401


def test_create_user_rejects_unknown_material_center(db_session: Session) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/auth/users",
            json={
                "username": "ghost.rep",
                "password": "a-real-password",
                "full_name": "Ghost Rep",
                "material_center_code": 999999,
            },
        )
        assert resp.status_code == 422


def test_create_user_rejects_duplicate_username(
    db_session: Session, test_user: User, material_center: MaterialCenter
) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/auth/users",
            json={
                "username": test_user.username,
                "password": "another-password",
                "full_name": "Someone Else",
                "material_center_code": material_center.busy_code,
            },
        )
        assert resp.status_code == 409
