"""app/domain/catalog/stock.py — UNVERIFIED against a real ground truth (see that
module's docstring and CLAUDE.md §8). These tests only prove the summing mechanism is
correct given real input shapes — they do NOT prove the computed totals match BUSY's
own GUI-displayed stock, which has never been cross-checked.

Fixtures below are the real Tran2 rows captured live 2026-08-15 for BUSY's two actual
stock-tracked items (Cable-infinix Micro, code 1613, and Cable-infinix Typ C, code
1614) — not invented data, per CLAUDE.md §5's testing discipline. Both items' only
real history is a Physical Stock opening entry (delta 0) plus one Stock Journal that
transfers quantity from 1613 to 1614 (their sums are exact negatives of each other:
-11 and +11 — strong internal evidence the sign convention is source-negative,
destination-positive, even though there's no independent way to confirm it from here).
"""

from decimal import Decimal

from app.domain.catalog.stock import StockMovement, compute_item_stock

# Real Tran2 rows for item 1613 (Cable-infinix Micro), captured live.
_ITEM_1613_MOVEMENTS = [
    StockMovement(vch_code=958, vch_type=61, rec_type=101, qty=Decimal("0")),  # Physical Stock
    StockMovement(vch_code=959, vch_type=8, rec_type=2, qty=Decimal("-10")),  # Stock Journal
    StockMovement(vch_code=960, vch_type=8, rec_type=2, qty=Decimal("-1")),  # Stock Journal
    StockMovement(vch_code=9733, vch_type=26, rec_type=20, qty=Decimal("1")),  # Sale Quotation
    StockMovement(vch_code=9734, vch_type=26, rec_type=20, qty=Decimal("1")),  # Sale Quotation
    StockMovement(vch_code=9735, vch_type=26, rec_type=20, qty=Decimal("1")),  # Sale Quotation
]

# Real Tran2 rows for item 1614 (Cable-infinix Typ C), captured live — the mirror side
# of the same Stock Journal transfer (VchCode 959/960 also appear against item 1613).
_ITEM_1614_MOVEMENTS = [
    StockMovement(vch_code=958, vch_type=61, rec_type=101, qty=Decimal("0")),  # Physical Stock
    StockMovement(vch_code=959, vch_type=8, rec_type=2, qty=Decimal("1")),  # Stock Journal
    StockMovement(vch_code=960, vch_type=8, rec_type=2, qty=Decimal("10")),  # Stock Journal
]


def test_compute_item_stock_excludes_quotation_lines() -> None:
    """The three Sale Quotation rows (RecType=20) must NOT count — quotations don't
    move stock. If they were mistakenly included the total would be -8, not -11."""
    assert compute_item_stock(_ITEM_1613_MOVEMENTS) == Decimal("-11")


def test_compute_item_stock_excludes_physical_stock_delta_of_zero() -> None:
    assert compute_item_stock(_ITEM_1614_MOVEMENTS) == Decimal("11")


def test_compute_item_stock_transfer_pair_nets_to_zero() -> None:
    """The Stock Journal moved quantity from 1613 to 1614 — summed across both items,
    the real movements (excluding quotations) should net to zero, consistent with a
    single transfer rather than two independent operational movements."""
    total = compute_item_stock(_ITEM_1613_MOVEMENTS) + compute_item_stock(_ITEM_1614_MOVEMENTS)
    assert total == Decimal("0")


def test_compute_item_stock_ignores_account_ledger_lines() -> None:
    movements = [
        StockMovement(vch_code=1, vch_type=9, rec_type=1, qty=Decimal("2000")),  # ledger, not item
        StockMovement(vch_code=1, vch_type=9, rec_type=2, qty=Decimal("-1")),  # real item movement
    ]
    assert compute_item_stock(movements) == Decimal("-1")


def test_compute_item_stock_empty_history_is_zero() -> None:
    assert compute_item_stock([]) == Decimal("0")
