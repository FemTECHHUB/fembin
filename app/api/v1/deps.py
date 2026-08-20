"""Shared FastAPI dependency annotations for the v1 API."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.domain.auth.tokens import InvalidTokenError, decode_access_token

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_bearer_scheme = HTTPBearer()


def get_current_user(
    db: DbSession,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> User:
    """Resolve a bearer token to a real, still-active `User` — every BUSY-affecting action
    is scoped to this user's material center (CLAUDE.md NFR6), not left as free-text
    caller input."""
    try:
        payload = decode_access_token(credentials.credentials, settings=settings)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from exc
    user = db.get(User, payload.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_superadmin(current_user: CurrentUser) -> User:
    """Same as CurrentUser, but 403s anyone who isn't a superadmin — for user management
    and the cross-branch admin dashboard, both of which must not be self-service."""
    if not current_user.is_superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "superadmin access required")
    return current_user


SuperadminUser = Annotated[User, Depends(get_current_superadmin)]
