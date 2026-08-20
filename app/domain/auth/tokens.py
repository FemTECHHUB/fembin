"""JWT access tokens — carry the user's identity and material center so route handlers can
scope actions to it directly from the token (CurrentUser in app/api/v1/deps.py still loads
the User row too, to catch a since-deactivated account)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings
from app.db.models import User


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or signed with the
    wrong key."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    username: str
    material_center_code: int


def create_access_token(user: User, *, settings: Settings) -> str:
    """Issue a signed, expiring access token for a just-authenticated user."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "material_center_code": user.material_center_code,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, *, settings: Settings) -> TokenPayload:
    """Verify and decode a bearer token, raising `InvalidTokenError` on any problem."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    try:
        return TokenPayload(
            user_id=int(payload["sub"]),
            username=payload["username"],
            material_center_code=payload["material_center_code"],
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError("malformed token payload") from exc
