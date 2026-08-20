"""Auth routes — thin (CLAUDE.md §3). User creation is deliberately open for now (there's
no admin/permissions system yet — the user explicitly chose to defer that); this must be
locked down before Sprint 5's pilot rollout, same as the outbox worker's current
single-process assumption."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DbSession, SettingsDep
from app.api.v1.schemas_auth import LoginRequest, TokenOut, UserCreateRequest, UserOut
from app.domain.auth.tokens import create_access_token
from app.domain.auth.users import (
    DuplicateUsernameError,
    InvalidCredentialsError,
    UnknownMaterialCenterError,
    authenticate_user,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/users", response_model=UserOut, status_code=201)
def create_user_route(body: UserCreateRequest, db: DbSession) -> UserOut:
    try:
        user = create_user(
            db,
            username=body.username,
            password=body.password,
            full_name=body.full_name,
            material_center_code=body.material_center_code,
        )
    except DuplicateUsernameError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "username already taken") from exc
    except UnknownMaterialCenterError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "material_center_code does not match a known, active material center",
        ) from exc
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
def login_route(body: LoginRequest, db: DbSession, settings: SettingsDep) -> TokenOut:
    try:
        user = authenticate_user(db, username=body.username, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password") from exc
    token = create_access_token(user, settings=settings)
    return TokenOut(access_token=token)
