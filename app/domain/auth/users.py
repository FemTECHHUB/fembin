"""User account management — create/authenticate app users, each tied to one
`MaterialCenter` so every action they take is scoped to a real branch (CLAUDE.md NFR6)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter, User
from app.domain.auth.passwords import hash_password, verify_password


class DuplicateUsernameError(Exception):
    """Raised when a username is already taken."""


class UnknownMaterialCenterError(Exception):
    """Raised when the given material center code doesn't exist in our mirror, or is
    inactive — a user must be tied to a real, currently-active branch."""


class InvalidCredentialsError(Exception):
    """Raised on a failed login — wrong username, wrong password, or an inactive user.
    Deliberately doesn't distinguish which, so failed logins don't leak which usernames
    exist."""


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    full_name: str,
    material_center_code: int,
) -> User:
    """Register a new app user tied to a material center. Fails loudly if the username is
    taken or the material center doesn't exist/isn't active — a user must always resolve to
    a real branch."""
    if session.scalar(select(User).where(User.username == username)) is not None:
        raise DuplicateUsernameError(username)

    material_center = session.get(MaterialCenter, material_center_code)
    if material_center is None or not material_center.is_active:
        raise UnknownMaterialCenterError(material_center_code)

    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        material_center_code=material_center_code,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, *, username: str, password: str) -> User:
    """Verify a login attempt, raising `InvalidCredentialsError` on any failure."""
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError(username)
    return user
