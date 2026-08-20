"""Sales-people routes — thin (CLAUDE.md §3). Listing is scoped to the caller's own
material center (any authenticated user, for their own "pick your name" dropdown);
creating one is superadmin-only, same lockdown reasoning as user creation."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import CurrentUser, DbSession, SuperadminUser
from app.api.v1.schemas_sales_people import SalesPersonCreateRequest, SalesPersonOut
from app.domain.orders.sales_people import (
    UnknownMaterialCenterError,
    create_sales_person,
    list_sales_people,
)

router = APIRouter(prefix="/sales-people", tags=["sales-people"])


@router.get("", response_model=list[SalesPersonOut])
def list_sales_people_route(db: DbSession, current_user: CurrentUser) -> list[SalesPersonOut]:
    people = list_sales_people(db, material_center_code=current_user.material_center_code)
    return [SalesPersonOut.model_validate(p) for p in people]


@router.post("", response_model=SalesPersonOut, status_code=201)
def create_sales_person_route(
    body: SalesPersonCreateRequest, db: DbSession, _: SuperadminUser
) -> SalesPersonOut:
    try:
        person = create_sales_person(
            db, full_name=body.full_name, material_center_code=body.material_center_code
        )
    except UnknownMaterialCenterError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "material_center_code does not match a known, active material center",
        ) from exc
    return SalesPersonOut.model_validate(person)
