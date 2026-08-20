"""Sale Quotation routes — thin (CLAUDE.md §3). Enqueueing is a local DB insert only
(app/domain/orders/quotations.py), never a direct BUSY call — safe to run inline, unlike
BUSY-touching endpoints elsewhere which hand off via BackgroundTasks instead.

Every route requires an authenticated user (CurrentUser, app/api/v1/deps.py): the material
center on the quotation is always the caller's own assigned branch (CLAUDE.md NFR6), never
client-supplied, and the listing is scoped to that same branch."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas_outbox import OutboxJobOut, QuotationCreateRequest
from app.db.models import MaterialCenter
from app.domain.orders.quotations import (
    QuotationItem,
    QuotationRequest,
    enqueue_sale_quotation,
    list_quotations,
)

router = APIRouter(prefix="/quotations", tags=["quotations"])


@router.get("", response_model=list[OutboxJobOut])
def list_sale_quotations_route(db: DbSession, current_user: CurrentUser) -> list[OutboxJobOut]:
    jobs = list_quotations(db, material_center_code=current_user.material_center_code)
    return [OutboxJobOut.model_validate(job) for job in jobs]


@router.post("", response_model=OutboxJobOut, status_code=202)
def create_sale_quotation_route(
    body: QuotationCreateRequest, db: DbSession, current_user: CurrentUser
) -> OutboxJobOut:
    material_center = db.get(MaterialCenter, current_user.material_center_code)
    if material_center is None:
        # Shouldn't happen — create_user validates this at signup — but a material
        # center could in principle be resynced away since. Fail loudly, don't guess.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "your assigned material center no longer exists in our mirror",
        )

    request = QuotationRequest(
        vch_series_name=body.vch_series_name,
        vch_no_prefix=body.vch_no_prefix,
        date=body.date,
        sale_type_name=body.sale_type_name,
        customer_name=body.customer_name,
        material_center_name=material_center.name,
        items=[
            QuotationItem(
                item_name=item.item_name,
                unit_name=item.unit_name,
                qty=item.qty,
                price=item.price,
                amount=item.amount,
            )
            for item in body.items
        ],
    )
    job = enqueue_sale_quotation(
        db,
        request,
        idempotency_key=body.idempotency_key,
        created_by_user_id=current_user.id,
        created_by_username=current_user.username,
        material_center_code=current_user.material_center_code,
    )
    return OutboxJobOut.model_validate(job)
