"""app/domain/orders/quotations.py.

Root tag, VchNo requirement, and STPTName requirement are all confirmed against live
BUSY 2026-08-15 (CLAUDE.md §8) — these tests prove the builder/enqueue/worker-handler
wiring is correct against that confirmed shape, using the mock BUSY server.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.busy.constants import VchType
from app.busy.xml_util import parse_element_xml
from app.domain.orders.quotations import (
    JOB_TYPE,
    QuotationItem,
    QuotationRequest,
    _handle_add_sale_quotation,
    _request_to_payload,
    _verify_and_price_items_from_busy,
    build_quotation_xml,
    enqueue_sale_quotation,
    list_quotations,
)
from app.outbox.models import OutboxStatus
from app.outbox.queue import enqueue
from app.outbox.worker import process_next_job


def _sample_request() -> QuotationRequest:
    return QuotationRequest(
        vch_series_name="Main",
        vch_no_prefix="RCC",
        date="15-08-2026",
        sale_type_name="Repair",
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


def _processable_request() -> QuotationRequest:
    """Like _sample_request, but item names/codes match the mock BUSY server's
    GetMasterXML fixture ("Fake Item {code}", tests/fixtures/mock_busy.py) so requests
    pass _verify_items_against_busy's live pre-post check — for tests that exercise the
    full handler/worker path (actually posting), not just XML building."""
    return QuotationRequest(
        vch_series_name="Main",
        vch_no_prefix="RCC",
        date="15-08-2026",
        sale_type_name="Repair",
        customer_name="O'Brien & Sons",
        material_center_name="Main Store",
        items=[
            QuotationItem(
                item_name="Fake Item 5001",
                unit_name="Pcs.",
                qty=Decimal("1"),
                price=Decimal("26000"),
                amount=Decimal("26000"),
                busy_code=5001,
            ),
            QuotationItem(
                item_name="Fake Item 5002",
                unit_name="Pcs.",
                qty=Decimal("2"),
                price=Decimal("500"),
                amount=Decimal("1000"),
                busy_code=5002,
            ),
        ],
    )


def test_build_quotation_xml_is_well_formed_and_round_trips() -> None:
    xml = build_quotation_xml(_sample_request(), vch_no="RCC-6")
    parsed = parse_element_xml(xml)
    assert isinstance(parsed, dict)
    quotation = parsed["SaleQuotation"]
    assert isinstance(quotation, dict)

    assert quotation["VchType"] == str(int(VchType.SALE_QUOTATION))
    assert quotation["VchNo"] == "RCC-6"
    assert quotation["STPTName"] == "Repair"
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


def test_enqueue_sale_quotation_creates_outbox_job_without_computing_vchno(
    db_session: Session,
) -> None:
    """VchNo isn't known yet at enqueue time — computing it here (rather than in the
    worker, at post time) would race two back-to-back quotations onto the same number."""
    job = enqueue_sale_quotation(
        db_session,
        _sample_request(),
        idempotency_key="quote-1",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )

    assert job.job_type == JOB_TYPE
    assert job.status == OutboxStatus.QUEUED
    assert job.payload["vch_no_prefix"] == "RCC"
    assert "vch_xml" not in job.payload
    assert job.payload["items"][0]["qty"] == "1"  # Decimal stored as str (JSON-safe)


async def test_handle_add_sale_quotation_computes_next_vchno_and_posts(
    busy_client: BusyClient,
) -> None:
    """Mock BUSY's fake "RCC" ledger (tests/fixtures/mock_busy.py) has RCC-1/2/5 —
    next must be RCC-6, proving the real max+1 lookup logic, not just the trivial
    empty-ledger case."""
    payload = _request_to_payload(_processable_request())
    result = await _handle_add_sale_quotation(payload, busy_client)

    assert result["vch_no"] == "RCC-6"
    assert "vch_code" in result


async def test_worker_processes_a_queued_sale_quotation_end_to_end(
    db_session: Session, busy_client: BusyClient
) -> None:
    enqueue_sale_quotation(
        db_session,
        _processable_request(),
        idempotency_key="quote-e2e",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.DONE
    assert processed.result is not None
    assert processed.result["vch_no"] == "RCC-6"


async def test_worker_leaves_unknown_prefix_starting_at_one(
    db_session: Session, busy_client: BusyClient
) -> None:
    request = QuotationRequest(
        vch_series_name="RC Taiwo",
        vch_no_prefix="JCT",  # no fake data registered for this prefix
        date="15-08-2026",
        sale_type_name="Repair",
        customer_name="Jane Doe",
        material_center_name="Repair Centre Taiwo",
        items=[
            QuotationItem(
                item_name="Fake Item 5003",
                unit_name="Pcs.",
                qty=Decimal("1"),
                price=Decimal("2000"),
                amount=Decimal("2000"),
                busy_code=5003,
            )
        ],
    )
    job = enqueue(
        db_session,
        job_type=JOB_TYPE,
        payload=_request_to_payload(request),
        idempotency_key="quote-jct",
    )
    assert job.status == OutboxStatus.QUEUED

    processed = await process_next_job(db_session, busy_client)
    assert processed is not None
    assert processed.result is not None
    assert processed.result["vch_no"] == "JCT-1"


def test_list_quotations_returns_most_recent_first(db_session: Session) -> None:
    first = enqueue_sale_quotation(
        db_session,
        _sample_request(),
        idempotency_key="list-1",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )
    second = enqueue_sale_quotation(
        db_session,
        _sample_request(),
        idempotency_key="list-2",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )

    jobs = list_quotations(db_session)

    assert [j.id for j in jobs] == [second.id, first.id]
    assert all(j.job_type == JOB_TYPE for j in jobs)


def test_list_quotations_scoped_to_material_center(db_session: Session) -> None:
    same_center = enqueue_sale_quotation(
        db_session,
        _sample_request(),
        idempotency_key="list-mc-201",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )
    enqueue_sale_quotation(
        db_session,
        _sample_request(),
        idempotency_key="list-mc-1155",
        created_by_user_id=2,
        created_by_username="jane.cashier",
        material_center_code=1155,
        sales_person_id=20,
        sales_person_name="Chidi Sales",
    )

    jobs = list_quotations(db_session, material_center_code=201)

    assert [j.id for j in jobs] == [same_center.id]


async def test_list_quotations_reflects_status_after_processing(
    db_session: Session, busy_client: BusyClient
) -> None:
    enqueue_sale_quotation(
        db_session,
        _processable_request(),
        idempotency_key="list-status",
        created_by_user_id=1,
        created_by_username="taiwo.rep",
        material_center_code=201,
        sales_person_id=10,
        sales_person_name="Femi Sales",
    )
    await process_next_job(db_session, busy_client)

    jobs = list_quotations(db_session)

    assert len(jobs) == 1
    assert jobs[0].status == OutboxStatus.DONE
    assert jobs[0].result is not None
    assert jobs[0].result["vch_no"] == "RCC-6"


async def test_verify_and_price_items_uses_busys_live_price_not_the_stale_one(
    busy_client: BusyClient,
) -> None:
    """Price must come from BUSY at post time, not whatever was captured at cart-add.
    The mock server's Fake Item 5001 always reports SalePrice=1000 regardless of what
    we send it, so a stale/wrong captured price (26000) must get overwritten, and
    `amount` must be recomputed from it rather than left stale too."""
    stale_request = QuotationRequest(
        vch_series_name="Main",
        vch_no_prefix="RCC",
        date="15-08-2026",
        sale_type_name="Repair",
        customer_name="Jane Doe",
        material_center_name="Main Store",
        items=[
            QuotationItem(
                item_name="Fake Item 5001",
                unit_name="Pcs.",
                qty=Decimal("3"),
                price=Decimal("26000"),  # stale — what the cashier saw at cart-add time
                amount=Decimal("78000"),
                busy_code=5001,
            )
        ],
    )

    refreshed = await _verify_and_price_items_from_busy(stale_request, busy_client)

    assert refreshed.items[0].price == Decimal("1000")
    assert refreshed.items[0].amount == Decimal("3000")  # qty(3) * live price(1000)


async def test_worker_rejects_item_name_mismatch_against_busy(
    db_session: Session, busy_client: BusyClient
) -> None:
    """The core protection this feature exists for: if what we're about to send doesn't
    match BUSY's live item master, refuse to post rather than let BUSY silently create a
    duplicate item under the wrong name."""
    request = QuotationRequest(
        vch_series_name="Main",
        vch_no_prefix="RCC",
        date="15-08-2026",
        sale_type_name="Repair",
        customer_name="Jane Doe",
        material_center_name="Main Store",
        items=[
            QuotationItem(
                item_name="Stale Old Name",  # mock reports "Fake Item 5001" for this code
                unit_name="Pcs.",
                qty=Decimal("1"),
                price=Decimal("1000"),
                amount=Decimal("1000"),
                busy_code=5001,
            )
        ],
    )
    enqueue(
        db_session,
        job_type=JOB_TYPE,
        payload=_request_to_payload(request),
        idempotency_key="quote-mismatch",
    )

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.FAILED
    assert processed.last_error is not None
    assert "Stale Old Name" in processed.last_error
    assert "Fake Item 5001" in processed.last_error


async def test_worker_rejects_item_missing_busy_code(
    db_session: Session, busy_client: BusyClient
) -> None:
    """An item with no linked product code can't be verified against BUSY at all —
    refuse to post rather than risk an unchecked duplicate/stale-price item."""
    request = QuotationRequest(
        vch_series_name="Main",
        vch_no_prefix="RCC",
        date="15-08-2026",
        sale_type_name="Repair",
        customer_name="Jane Doe",
        material_center_name="Main Store",
        items=[
            QuotationItem(
                item_name="No Code Item",
                unit_name="Pcs.",
                qty=Decimal("1"),
                price=Decimal("1000"),
                amount=Decimal("1000"),
                # busy_code intentionally omitted — defaults to None
            )
        ],
    )
    enqueue(
        db_session,
        job_type=JOB_TYPE,
        payload=_request_to_payload(request),
        idempotency_key="quote-no-code",
    )

    processed = await process_next_job(db_session, busy_client)

    assert processed is not None
    assert processed.status == OutboxStatus.FAILED
    assert processed.last_error is not None
    assert "no linked product code" in processed.last_error
