"""Superadmin dashboard routes — thin (CLAUDE.md §3). Every route here is unscoped by
material center (unlike the regular per-branch routes) and gated on SuperadminUser."""

from fastapi import APIRouter

from app.api.v1.deps import DbSession, SuperadminUser
from app.api.v1.schemas_auth import UserOut
from app.api.v1.schemas_outbox import OutboxJobOut
from app.api.v1.schemas_sales_people import SalesPersonOut
from app.domain.auth.users import list_users
from app.domain.catalog.queries import list_salesmen
from app.domain.orders.quotations import list_quotations

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
    # Includes inactive (blocked/deactivated in BUSY) ones — GET /api/v1/sales-people
    # (the caller-facing picker) only ever shows active ones.
    people = list_salesmen(db, active_only=False)
    return [SalesPersonOut.model_validate(p) for p in people]
