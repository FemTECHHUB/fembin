"""app/domain/orders/quotations.py — the XML shape is UNVERIFIED against real BUSY (see
CLAUDE.md §8). These tests only prove the builder is internally consistent and enqueues
correctly, not that BUSY actually accepts this shape.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.busy.constants import VchType
from app.busy.xml_util import parse_element_xml
from app.domain.orders.quotations import (
    QuotationItem,
    QuotationRequest,
    build_quotation_xml,
    enqueue_sale_quotation,
)
from app.outbox.models import OutboxStatus


def _sample_request() -> QuotationRequest:
    return QuotationRequest(
        vch_series_name="Main",
        date="15-08-2026",
        sale_type_name="Local-ItemWise",
        customer_name="O'Brien & Sons",
        material_center_name="Main Store",
        items=[
            QuotationItem(
                item_name="Acer Laptop",
                unit_name="Pcs.",
                qty=Decimal("1"),
                price=Decimal("26000"),
                amount=Decimal("26000"),
            ),
            QuotationItem(
                item_name="Mouse",
                unit_name="Pcs.",
                qty=Decimal("2"),
                price=Decimal("500"),
                amount=Decimal("1000"),
            ),
        ],
    )


def test_build_quotation_xml_is_well_formed_and_round_trips() -> None:
    xml = build_quotation_xml(_sample_request())
    parsed = parse_element_xml(xml)
    assert isinstance(parsed, dict)
    quotation = parsed["SaleQuotation"]
    assert isinstance(quotation, dict)

    assert quotation["VchType"] == str(int(VchType.SALE_QUOTATION))
    assert quotation["MasterName1"] == "O'Brien & Sons"  # entity-encode/decode round trip

    item_entries = quotation["ItemEntries"]
    assert isinstance(item_entries, dict)
    items = item_entries["ItemDetail"]
    assert isinstance(items, list)
    assert len(items) == 2
    first_item, second_item = items[0], items[1]
    assert isinstance(first_item, dict)
    assert isinstance(second_item, dict)
    assert first_item["ItemName"] == "Acer Laptop"
    assert second_item["ItemName"] == "Mouse"


def test_enqueue_sale_quotation_creates_outbox_job(db_session: Session) -> None:
    job = enqueue_sale_quotation(db_session, _sample_request(), idempotency_key="quote-1")

    assert job.job_type == "add_voucher"
    assert job.status == OutboxStatus.QUEUED
    assert job.payload["vch_type"] == int(VchType.SALE_QUOTATION)
    assert "<SaleQuotation>" in job.payload["vch_xml"]
