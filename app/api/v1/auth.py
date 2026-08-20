"""Auth routes — thin (CLAUDE.md §3). User creation requires an existing superadmin
(locked down 2026-08-20, at explicit request — the first superadmin must be created via
scripts/create_superadmin.py, not over HTTP, to avoid a self-service admin hole)."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import CurrentUser, DbSession, SettingsDep, SuperadminUser
from app.api.v1.schemas_auth import (
    CurrentUserOut,
    LoginRequest,
    TokenOut,
    UserCreateRequest,
    UserOut,
)
from app.db.models import MaterialCenter
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
def create_user_route(body: UserCreateRequest, db: DbSession, _: SuperadminUser) -> UserOut:
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


@router.get("/me", response_model=CurrentUserOut)
def current_user_route(current_user: CurrentUser, db: DbSession) -> CurrentUserOut:
    material_center = db.get(MaterialCenter, current_user.material_center_code)
    material_center_name = material_center.name if material_center is not None else "(unknown)"
    return CurrentUserOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        material_center_code=current_user.material_center_code,
        material_center_name=material_center_name,
        is_superadmin=current_user.is_superadmin,
    )
