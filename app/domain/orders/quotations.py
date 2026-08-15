"""Sale Quotations (BUSY VchType=26) — a quote sent to a customer, not yet a sale.

Confirmed against live BUSY 2026-08-15 (CLAUDE.md §8 has the full writeup):
  - Root tag `<SaleQuotation>` is correct.
  - This company has Detailed Audit Trail enabled, so `VchNo` must be a real
    "<prefix>-<n>" for the chosen series, computed via app.busy.vch_numbering — an
    arbitrary or omitted `VchNo` is rejected ("Voucher number can not be blank").
  - `STPTName` (Sale Type) must be a real one for the target company — there is no
    universal default; the caller must supply one that actually exists in their data.

`VchNo` is deliberately computed in the OUTBOX WORKER (`_handle_add_sale_quotation`),
not at enqueue time: computing it early risks two quotations enqueued back-to-back
both computing the *same* next number, since neither has posted yet to advance BUSY's
own ledger. The worker processes one job at a time to completion (CLAUDE.md §2.2 — no
concurrency), so by the time each job's `VchNo` is computed, every prior job has
already posted and moved BUSY's ledger forward.

Enqueues onto the outbox (app/outbox/) rather than calling BUSY directly — CLAUDE.md
§2.2, no exceptions for any SC=2 write, quotations included.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.busy.constants import VchType
from app.busy.vch_numbering import get_next_vch_no
from app.busy.xml_util import encode_xml_entities
from app.outbox.models import OutboxJob
from app.outbox.queue import enqueue
from app.outbox.worker import register_handler

JOB_TYPE = "add_sale_quotation"


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
    vch_no_prefix: str  # e.g. "RCC" for the "Main" series — discovered, not derivable
    date: str  # DD-MM-YYYY, matching the confirmed live-tested format
    sale_type_name: str
    customer_name: str
    material_center_name: str
    items: list[QuotationItem]


def build_quotation_xml(request: QuotationRequest, *, vch_no: str) -> str:
    """Build the `<SaleQuotation>` XML body for SC=2 (`VchXml` header)."""
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
        f"<VchNo>{encode_xml_entities(vch_no)}</VchNo>"
        f"<STPTName>{encode_xml_entities(request.sale_type_name)}</STPTName>"
        f"<MasterName1>{encode_xml_entities(request.customer_name)}</MasterName1>"
        f"<MasterName2>{encode_xml_entities(request.material_center_name)}</MasterName2>"
        f"<ItemEntries>{item_tags}</ItemEntries>"
        "</SaleQuotation>"
    )


def _request_to_payload(request: QuotationRequest) -> dict[str, Any]:
    # Decimal isn't JSON-serializable (the outbox payload column is JSON) — stringify.
    return {
        "vch_series_name": request.vch_series_name,
        "vch_no_prefix": request.vch_no_prefix,
        "date": request.date,
        "sale_type_name": request.sale_type_name,
        "customer_name": request.customer_name,
        "material_center_name": request.material_center_name,
        "items": [
            {
                "item_name": item.item_name,
                "unit_name": item.unit_name,
                "qty": str(item.qty),
                "price": str(item.price),
                "amount": str(item.amount),
            }
            for item in request.items
        ],
    }


def _payload_to_request(payload: dict[str, Any]) -> QuotationRequest:
    items = [
        QuotationItem(
            item_name=item["item_name"],
            unit_name=item["unit_name"],
            qty=Decimal(item["qty"]),
            price=Decimal(item["price"]),
            amount=Decimal(item["amount"]),
        )
        for item in payload["items"]
    ]
    return QuotationRequest(
        vch_series_name=payload["vch_series_name"],
        vch_no_prefix=payload["vch_no_prefix"],
        date=payload["date"],
        sale_type_name=payload["sale_type_name"],
        customer_name=payload["customer_name"],
        material_center_name=payload["material_center_name"],
        items=items,
    )


def enqueue_sale_quotation(
    session: Session, request: QuotationRequest, *, idempotency_key: str
) -> OutboxJob:
    """Just a local DB insert (app/outbox/queue.py) — safe to call inline from a request
    handler. `VchNo` isn't computed yet; that happens in the worker, at post time (see
    module docstring for why)."""
    return enqueue(
        session,
        job_type=JOB_TYPE,
        payload=_request_to_payload(request),
        idempotency_key=idempotency_key,
    )


def list_quotations(session: Session) -> list[OutboxJob]:
    """Every Sale Quotation ever enqueued, most recent first — status (queued/running/
    done/failed) plus the BUSY-assigned VchNo/VchCode once processed, so a caller can
    see exactly which ones have actually been posted vs. still pending."""
    stmt = select(OutboxJob).where(OutboxJob.job_type == JOB_TYPE).order_by(OutboxJob.id.desc())
    return list(session.scalars(stmt))


async def _handle_add_sale_quotation(payload: dict[str, Any], busy: BusyClient) -> dict[str, Any]:
    request = _payload_to_request(payload)
    vch_no = await get_next_vch_no(busy, int(VchType.SALE_QUOTATION), request.vch_no_prefix)
    xml = build_quotation_xml(request, vch_no=vch_no)
    vch_code = await busy.add_voucher(int(VchType.SALE_QUOTATION), xml)
    return {"vch_code": vch_code, "vch_no": vch_no}


register_handler(JOB_TYPE, _handle_add_sale_quotation)
