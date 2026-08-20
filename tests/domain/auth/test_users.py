"""app/domain/auth/users.py — create_user/authenticate_user, each tied to a real
MaterialCenter (CLAUDE.md NFR6)."""

import pytest
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter
from app.domain.auth.users import (
    DuplicateUsernameError,
    InvalidCredentialsError,
    UnknownMaterialCenterError,
    authenticate_user,
    create_user,
)


def test_create_user_ties_to_a_real_material_center(
    db_session: Session, material_center: MaterialCenter
) -> None:
    user = create_user(
        db_session,
        username="taiwo.rep",
        password="test-pass-123",
        full_name="Taiwo Adeyemi",
        material_center_code=material_center.busy_code,
    )

    assert user.id is not None
    assert user.material_center_code == material_center.busy_code
    assert user.password_hash != "test-pass-123"  # never stored as plaintext


def test_create_user_rejects_unknown_material_center(db_session: Session) -> None:
    with pytest.raises(UnknownMaterialCenterError):
        create_user(
            db_session,
            username="ghost.rep",
            password="test-pass-123",
            full_name="Ghost Rep",
            material_center_code=999999,
        )


def test_create_user_rejects_inactive_material_center(db_session: Session) -> None:
    inactive = MaterialCenter(busy_code=555, name="Closed Branch", is_active=False)
    db_session.add(inactive)
    db_session.commit()

    with pytest.raises(UnknownMaterialCenterError):
        create_user(
            db_session,
            username="rep.at.closed",
            password="test-pass-123",
            full_name="Rep",
            material_center_code=555,
        )


def test_create_user_rejects_duplicate_username(
    db_session: Session, material_center: MaterialCenter
) -> None:
    create_user(
        db_session,
        username="taiwo.rep",
        password="test-pass-123",
        full_name="Taiwo Adeyemi",
        material_center_code=material_center.busy_code,
    )
    with pytest.raises(DuplicateUsernameError):
        create_user(
            db_session,
            username="taiwo.rep",
            password="a-different-password",
            full_name="Someone Else",
            material_center_code=material_center.busy_code,
        )


def test_authenticate_user_succeeds_with_correct_credentials(
    db_session: Session, material_center: MaterialCenter
) -> None:
    create_user(
        db_session,
        username="taiwo.rep",
        password="test-pass-123",
        full_name="Taiwo Adeyemi",
        material_center_code=material_center.busy_code,
    )

    user = authenticate_user(db_session, username="taiwo.rep", password="test-pass-123")
    assert user.username == "taiwo.rep"


def test_authenticate_user_rejects_wrong_password(
    db_session: Session, material_center: MaterialCenter
) -> None:
    create_user(
        db_session,
        username="taiwo.rep",
        password="test-pass-123",
        full_name="Taiwo Adeyemi",
        material_center_code=material_center.busy_code,
    )

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, username="taiwo.rep", password="wrong-password")


def test_authenticate_user_rejects_unknown_username(db_session: Session) -> None:
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, username="nobody", password="whatever")


def test_authenticate_user_rejects_inactive_user(
    db_session: Session, material_center: MaterialCenter
) -> None:
    user = create_user(
        db_session,
        username="taiwo.rep",
        password="test-pass-123",
        full_name="Taiwo Adeyemi",
        material_center_code=material_center.busy_code,
    )
    user.is_active = False
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, username="taiwo.rep", password="test-pass-123")
