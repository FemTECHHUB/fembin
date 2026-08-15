"""Sale Quotation routes — thin (CLAUDE.md §3). Enqueueing is a local DB insert only
(app/domain/orders/quotations.py), never a direct BUSY call — safe to run inline, unlike
BUSY-touching endpoints elsewhere which hand off via BackgroundTasks instead."""

from fastapi import APIRouter

from app.api.v1.deps import DbSession
from app.api.v1.schemas_outbox import OutboxJobOut, QuotationCreateRequest
from app.domain.orders.quotations import QuotationItem, QuotationRequest, enqueue_sale_quotation

router = APIRouter(prefix="/quotations", tags=["quotations"])


@router.post("", response_model=OutboxJobOut, status_code=202)
def create_sale_quotation_route(body: QuotationCreateRequest, db: DbSession) -> OutboxJobOut:
    request = QuotationRequest(
        vch_series_name=body.vch_series_name,
        date=body.date,
        sale_type_name=body.sale_type_name,
        customer_name=body.customer_name,
        material_center_name=body.material_center_name,
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
    job = enqueue_sale_quotation(db, request, idempotency_key=body.idempotency_key)
    return OutboxJobOut.model_validate(job)
