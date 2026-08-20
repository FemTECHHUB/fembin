"""app/domain/auth/tokens.py — JWT issuance/verification."""

import pytest

from app.config import Settings
from app.db.models import User
from app.domain.auth.tokens import InvalidTokenError, create_access_token, decode_access_token


def _settings(
    *, jwt_secret_key: str = "test-secret-key-long-enough-for-hs256", jwt_expire_minutes: int = 480
) -> Settings:
    return Settings(jwt_secret_key=jwt_secret_key, jwt_expire_minutes=jwt_expire_minutes)


def _user() -> User:
    return User(
        id=1,
        username="taiwo.rep",
        password_hash="irrelevant-here",
        full_name="Taiwo Adeyemi",
        material_center_code=201,
    )


def test_create_and_decode_access_token_round_trips() -> None:
    settings = _settings()
    token = create_access_token(_user(), settings=settings)

    payload = decode_access_token(token, settings=settings)

    assert payload.user_id == 1
    assert payload.username == "taiwo.rep"
    assert payload.material_center_code == 201


def test_decode_access_token_rejects_wrong_secret() -> None:
    token = create_access_token(
        _user(), settings=_settings(jwt_secret_key="secret-a-long-enough-for-hs256")
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(
            token, settings=_settings(jwt_secret_key="secret-b-long-enough-for-hs256")
        )


def test_decode_access_token_rejects_expired_token() -> None:
    token = create_access_token(_user(), settings=_settings(jwt_expire_minutes=-1))

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings=_settings())


def test_decode_access_token_rejects_garbage() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-real-token", settings=_settings())
