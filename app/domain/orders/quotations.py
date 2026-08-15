"""Sale Quotations (BUSY VchType=26) — a quote sent to a customer, not yet a sale.

⚠️ UNVERIFIED XML SHAPE. Unlike Sale (VchType=9, confirmed against real BUSY data —
docs/reference/04-examples.md §4.3), no real Sale Quotation XML has ever been captured
or posted against live BUSY. `build_quotation_xml` below is inferred by analogy to that
one confirmed Sale example — same `<ItemEntries>`/`<ItemDetail>` shape, tax/discount
fields omitted since those would be pure guessing on top of an already-unverified base —
with only the root tag swapped to `<SaleQuotation>`. That swap itself is unconfirmed.
Tracked centrally in CLAUDE.md §8 (BUSY gotchas table); verify with one real test post
against the BUSY test company before trusting this in production (same "post one real
test voucher" recommendation as PRD §11 makes for Sale postings generally).

Enqueues onto the outbox (app/outbox/) rather than calling BUSY directly — CLAUDE.md §2.2,
no exceptions for any SC=2 write, quotations included.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.busy.constants import VchType
from app.busy.xml_util import encode_xml_entities
from app.outbox.models import OutboxJob
from app.outbox.queue import enqueue


@dataclass(frozen=True)
class QuotationItem:
    item_name: str
    unit_name: str
    qty: Decimal
    price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class QuotationRequest:
    vch_series_name: str
    date: str  # DD-MM-YYYY, matching the confirmed Sale example's format
    sale_type_name: str
    customer_name: str
    material_center_name: str
    items: list[QuotationItem]


def build_quotation_xml(request: QuotationRequest) -> str:
    """Build the `<SaleQuotation>` XML body for SC=2 (`VchXml` header). `VchNo` is
    deliberately omitted so BUSY auto-numbers it (PRD NFR5: dedicated series,
    auto-numbering on)."""
    item_tags = "".join(
        f"<ItemDetail><SrNo>{i}</SrNo>"
        f"<ItemName>{encode_xml_entities(item.item_name)}</ItemName>"
        f"<UnitName>{encode_xml_entities(item.unit_name)}</UnitName>"
        f"<Qty>{item.qty}</Qty><Price>{item.price}</Price><Amt>{item.amount}</Amt>"
        f"<MC>{encode_xml_entities(request.material_center_name)}</MC></ItemDetail>"
        for i, item in enumerate(request.items, start=1)
    )
    return (
        "<SaleQuotation>"
        f"<VchSeriesName>{encode_xml_entities(request.vch_series_name)}</VchSeriesName>"
        f"<Date>{request.date}</Date>"
        f"<VchType>{int(VchType.SALE_QUOTATION)}</VchType>"
        f"<STPTName>{encode_xml_entities(request.sale_type_name)}</STPTName>"
        f"<MasterName1>{encode_xml_entities(request.customer_name)}</MasterName1>"
        f"<MasterName2>{encode_xml_entities(request.material_center_name)}</MasterName2>"
        f"<ItemEntries>{item_tags}</ItemEntries>"
        "</SaleQuotation>"
    )


def enqueue_sale_quotation(
    session: Session, request: QuotationRequest, *, idempotency_key: str
) -> OutboxJob:
    """Just a local DB insert (app/outbox/queue.py) — safe to call inline from a request
    handler. The actual BUSY post happens later, out of band, in the outbox worker."""
    vch_xml = build_quotation_xml(request)
    return enqueue(
        session,
        job_type="add_voucher",
        payload={"vch_type": int(VchType.SALE_QUOTATION), "vch_xml": vch_xml},
        idempotency_key=idempotency_key,
    )
