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

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy.client import BusyClient, BusyError
from app.busy.constants import VchType
from app.busy.vch_numbering import get_next_vch_no
from app.busy.xml_util import encode_xml_entities, parse_element_xml
from app.db.models import Product
from app.db.session import SessionLocal
from app.domain.catalog.sync import apply_live_product_snapshot
from app.outbox.models import OutboxJob
from app.outbox.queue import enqueue
from app.outbox.worker import register_handler

logger = logging.getLogger(__name__)

JOB_TYPE = "add_sale_quotation"


class ItemMismatchError(Exception):
    """Raised when a quotation item can't be verified against BUSY's live item master
    right before posting — refusing to post rather than let BUSY silently create a
    duplicate item under a stale/wrong name (see _verify_items_against_busy)."""


@dataclass(frozen=True)
class QuotationItem:
    item_name: str
    unit_name: str
    qty: Decimal
    price: Decimal
    amount: Decimal
    # Stable identity for the item, independent of its display name — a job can sit
    # QUEUED for a long time (BUSY/network outages, backlog), during which the item's
    # name in BUSY may have changed. Posting a stale name makes BUSY fail to match an
    # existing item and silently create a new one under the old name (observed live).
    # `None` only for jobs enqueued before this field existed (backward compatibility).
    busy_code: int | None = None


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
                "busy_code": item.busy_code,
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
            busy_code=item.get("busy_code"),
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
    session: Session,
    request: QuotationRequest,
    *,
    idempotency_key: str,
    created_by_user_id: int,
    created_by_username: str,
    material_center_code: int,
    sales_person_id: int,
    sales_person_name: str,
) -> OutboxJob:
    """Just a local DB insert (app/outbox/queue.py) — safe to call inline from a request
    handler. `VchNo` isn't computed yet; that happens in the worker, at post time (see
    module docstring for why).

    `created_by_*`/`material_center_code` record which authenticated user (CLAUDE.md NFR6)
    and branch this action belongs to; `sales_person_*` records which named individual
    actually made the sale (distinct from the logged-in user — several people may share
    one login). All stored alongside the request, not inside the BUSY XML itself
    (SaleQuotation has no confirmed Narration/Remarks field to stamp identity into; see
    CLAUDE.md §8)."""
    payload = _request_to_payload(request)
    payload["created_by_user_id"] = created_by_user_id
    payload["created_by_username"] = created_by_username
    payload["material_center_code"] = material_center_code
    payload["sales_person_id"] = sales_person_id
    payload["sales_person_name"] = sales_person_name
    return enqueue(
        session,
        job_type=JOB_TYPE,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def list_quotations(
    session: Session, *, material_center_code: int | None = None
) -> list[OutboxJob]:
    """Every Sale Quotation ever enqueued, most recent first — status (queued/running/
    done/failed) plus the BUSY-assigned VchNo/VchCode once processed, so a caller can
    see exactly which ones have actually been posted vs. still pending.

    `material_center_code`, when given, scopes the list to quotations created by a user
    tied to that branch (CLAUDE.md NFR6) — filtered in Python rather than SQL since it
    lives inside the generic outbox `payload` JSON, not a dedicated column (the outbox is
    shared infrastructure for every future job type, not just quotations)."""
    stmt = select(OutboxJob).where(OutboxJob.job_type == JOB_TYPE).order_by(OutboxJob.id.desc())
    jobs = list(session.scalars(stmt))
    if material_center_code is not None:
        jobs = [
            job for job in jobs if job.payload.get("material_center_code") == material_center_code
        ]
    return jobs


_CENTS = Decimal("0.01")


def _with_current_item_data(request: QuotationRequest) -> QuotationRequest:
    """Re-resolve each item's name AND price from our (regularly-synced) product mirror
    right before posting — not at enqueue time. A job can sit QUEUED for hours or days
    (BUSY outage, backlog); what the cashier saw when adding to cart can be stale by the
    time it actually posts.

    Name: BUSY matches Sale Quotation items by name, not a stable code, so a stale name
    doesn't fail loudly — it silently creates a *new* item master under the old name
    (observed live, 2026-09-06).

    Price: deliberately refreshed too (business decision, not a technical necessity like
    the name) — a Quotation is a draft, not a finalized Sale, so it should reflect
    current pricing rather than a possibly-hours-stale snapshot. `amount` is recomputed
    from the refreshed price so it never drifts out of sync (qty * price).

    Falls back to the originally captured name/price if the code is missing (older jobs)
    or no longer in our mirror."""
    codes = [item.busy_code for item in request.items if item.busy_code is not None]
    if not codes:
        return request

    with SessionLocal() as session:
        current = {
            product.busy_code: product
            for product in session.query(Product).filter(Product.busy_code.in_(codes))
        }

    if not current:
        return request

    refreshed_items = [
        (
            item
            if item.busy_code is None or item.busy_code not in current
            else QuotationItem(
                item_name=current[item.busy_code].name,
                unit_name=item.unit_name,
                qty=item.qty,
                price=current[item.busy_code].price,
                amount=(item.qty * current[item.busy_code].price).quantize(_CENTS),
                busy_code=item.busy_code,
            )
        )
        for item in request.items
    ]
    return QuotationRequest(
        vch_series_name=request.vch_series_name,
        vch_no_prefix=request.vch_no_prefix,
        date=request.date,
        sale_type_name=request.sale_type_name,
        customer_name=request.customer_name,
        material_center_name=request.material_center_name,
        items=refreshed_items,
    )


async def _verify_and_price_items_from_busy(
    request: QuotationRequest, busy: BusyClient
) -> QuotationRequest:
    """Hard gate + authoritative price, right before posting — one BUSY call per item,
    read fresh this instant, not from our local mirror (which is only as fresh as the
    last catalog sync, currently ~5-10s):

    Name: confirm the name we're about to send — already refreshed from our local
    mirror by _with_current_item_data — still matches BUSY's *live* item master.
    BUSY's Sale Quotation API matches item lines by name, not our stable busy_code — a
    mismatch doesn't fail loudly on BUSY's side, it silently creates a *new* item master
    under whatever name we sent (observed live, 2026-09-06, a real duplicate resulted).
    Raising here turns that into a loud, visible FAILED job instead of silent corruption.

    Price: always overwritten with BUSY's live SalePrice from this same call — price
    is more consequential than a rename, so it gets the strongest guarantee available:
    read directly from BUSY at the moment of posting, zero staleness, not even the
    local-mirror sync interval. `amount` is recomputed from it so the two never drift
    apart. This is a business decision (a Quotation is a draft, not a finalized Sale,
    so it should reflect current pricing), not a technical requirement like the name."""
    refreshed_items = []
    with SessionLocal() as session:
        for item in request.items:
            if item.busy_code is None:
                raise ItemMismatchError(
                    f"item {item.item_name!r} has no linked product code — cannot "
                    "verify against BUSY; refusing to post rather than risk creating a "
                    "duplicate item or posting a stale price (resubmit from an "
                    "up-to-date POS session)"
                )
            try:
                detail_xml = await busy.get_master_xml(item.busy_code)
            except BusyError as exc:
                raise ItemMismatchError(
                    f"product code {item.busy_code} ({item.item_name!r}) could not be "
                    f"read back from BUSY to verify: {exc}"
                ) from exc

            parsed = parse_element_xml(detail_xml)
            node = parsed.get("Item", parsed) if isinstance(parsed, dict) else parsed
            if not isinstance(node, dict):
                raise ItemMismatchError(
                    f"product code {item.busy_code}: unexpected GetMasterXML shape " "from BUSY"
                )
            live_name = str(node.get("Name", ""))
            live_price = Decimal(str(node.get("SalePrice") or 0))

            if live_name != item.item_name:
                raise ItemMismatchError(
                    f"product code {item.busy_code}: about to send {item.item_name!r} "
                    f"but BUSY's current name for this item is {live_name!r} — "
                    "refusing to post to avoid creating a duplicate item in BUSY "
                    "(catalog sync should pick this up within seconds; retry once it "
                    "does)"
                )

            # Reuse the live read we already paid for — freshens our mirror (and thus
            # the POS display) for free, on top of whatever the periodic catalog sync
            # loop is already doing. Best-effort: a failure here shouldn't block the
            # actual quotation, which is the point of this call.
            try:
                apply_live_product_snapshot(
                    session, code=item.busy_code, name=live_name, price=live_price
                )
            except Exception:
                logger.warning(
                    "product %s: failed to opportunistically refresh local mirror "
                    "(non-fatal, continuing with the quotation)",
                    item.busy_code,
                    exc_info=True,
                )

            refreshed_items.append(
                QuotationItem(
                    item_name=item.item_name,
                    unit_name=item.unit_name,
                    qty=item.qty,
                    price=live_price,
                    amount=(item.qty * live_price).quantize(_CENTS),
                    busy_code=item.busy_code,
                )
            )

    return QuotationRequest(
        vch_series_name=request.vch_series_name,
        vch_no_prefix=request.vch_no_prefix,
        date=request.date,
        sale_type_name=request.sale_type_name,
        customer_name=request.customer_name,
        material_center_name=request.material_center_name,
        items=refreshed_items,
    )


async def _handle_add_sale_quotation(payload: dict[str, Any], busy: BusyClient) -> dict[str, Any]:
    request = _with_current_item_data(_payload_to_request(payload))
    request = await _verify_and_price_items_from_busy(request, busy)
    vch_no = await get_next_vch_no(busy, int(VchType.SALE_QUOTATION), request.vch_no_prefix)
    xml = build_quotation_xml(request, vch_no=vch_no)
    vch_code = await busy.add_voucher(int(VchType.SALE_QUOTATION), xml)
    return {"vch_code": vch_code, "vch_no": vch_no}


register_handler(JOB_TYPE, _handle_add_sale_quotation)
