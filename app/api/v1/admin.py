"""Superadmin dashboard routes — thin (CLAUDE.md §3). Every route here is unscoped by
material center (unlike the regular per-branch routes) and gated on SuperadminUser."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DbSession, SuperadminUser
from app.api.v1.schemas_auth import UserOut
from app.api.v1.schemas_outbox import OutboxJobOut
from app.api.v1.schemas_sales_people import SalesPersonOut, SalesPersonReassignRequest
from app.domain.auth.users import list_users
from app.domain.orders.quotations import list_quotations
from app.domain.orders.sales_people import (
    SalesPersonNotFoundError,
    UnknownMaterialCenterError,
    list_sales_people,
    reassign_sales_person,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_all_users_route(db: DbSession, _: SuperadminUser) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in list_users(db)]


@router.get("/quotations", response_model=list[OutboxJobOut])
def list_all_quotations_route(db: DbSession, _: SuperadminUser) -> list[OutboxJobOut]:
    jobs = list_quotations(db)  # no material_center_code filter — every branch
    return [OutboxJobOut.model_validate(job) for job in jobs]


@router.get("/sales-people", response_model=list[SalesPersonOut])
def list_all_sales_people_route(db: DbSession, _: SuperadminUser) -> list[SalesPersonOut]:
    people = list_sales_people(db, active_only=False)  # every branch, including inactive
    return [SalesPersonOut.model_validate(p) for p in people]


@router.patch("/sales-people/{sales_person_id}", response_model=SalesPersonOut)
def reassign_sales_person_route(
    sales_person_id: int, body: SalesPersonReassignRequest, db: DbSession, _: SuperadminUser
) -> SalesPersonOut:
    try:
        person = reassign_sales_person(
            db,
            sales_person_id,
            material_center_code=body.material_center_code,
            is_active=body.is_active,
        )
    except SalesPersonNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sales person not found") from exc
    except UnknownMaterialCenterError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "material_center_code does not match a known, active material center",
        ) from exc
    return SalesPersonOut.model_validate(person)
