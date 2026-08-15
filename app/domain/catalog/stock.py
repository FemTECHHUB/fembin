"""Derives item stock from BUSY transaction history (`Tran2`) — PRD §5's previously
unsolved problem ("Stock isn't on the Item master").

⚠️ UNVERIFIED AGAINST A GROUND TRUTH. This mechanism is built from real, confirmed
column semantics (live queries against Tran2, 2026-08-15 — CLAUDE.md §8 has the full
writeup) but has never been cross-checked against BUSY's own GUI-displayed stock
figure for any item, because this environment has no way to see that GUI. Do not wire
this into the catalog sync (i.e. do not start writing a `stock` value onto `products`)
until a human confirms the computed number against BUSY's GUI for at least one real
item with genuine (non-test) transaction history — same "verify before leaning on it
harder" discipline as the `Stamp`-granularity gotcha already in CLAUDE.md §8.

Confirmed column semantics:
  - `Tran2.RecType=2` rows are item-quantity-movement lines: `MasterCode1`=Item code,
    `MasterCode2`=Material Center code, `Value1`=signed Qty movement, `Value3`=signed
    monetary amount. `RecType=1` rows are ledger/account entries (not item
    movements) — exclude them.
  - `RecType=20` is a Sale/Purchase *Quotation* item line. Quotations don't move stock
    (confirmed: BUSY records the quantity but it's not a real movement) — so
    `RecType=20` must be excluded too, not just filtered by `VchType`.
  - `ItemBal1/2/3` and `Balance1/2/3` were `0` in every real row observed, including
    genuine stock-affecting Stock Journal entries on a stock-tracked item — BUSY does
    NOT appear to maintain a usable running balance for this company. Stock must be
    derived by summing raw movements, not read from a precomputed column.
  - A Physical Stock voucher (`VchType=61`) most likely represents an absolute count
    that resets the running total as of that date, not an additive delta — standard
    accounting-software semantics — but this is INFERRED, not confirmed: the one real
    example observed had a delta of `0`, which is consistent with either
    interpretation. This module currently treats it as just another additive delta.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.busy.client import BusyClient
from app.busy.constants import VchType
from app.busy.xml_util import parse_rowset_xml

ITEM_MOVEMENT_REC_TYPE = 2

# Voucher types that represent a real stock movement. Sale/Purchase Order and
# Sale/Purchase Quotation are deliberately excluded — they reserve or quote, they
# don't move stock (confirmed live: Sale Quotation item lines use RecType=20, not the
# RecType=2 used by genuine movements, which is why filtering on RecType alone would
# already exclude them — this list is a second, explicit line of defense).
STOCK_MOVING_VCH_TYPES = frozenset(
    {
        int(VchType.PURCHASE),
        int(VchType.SALE_RETURN),
        int(VchType.MATERIAL_RECEIPT),
        int(VchType.STOCK_TRANSFER),
        int(VchType.PRODUCTION),
        int(VchType.UNASSEMBLE),
        int(VchType.STOCK_JOURNAL),
        int(VchType.SALE),
        int(VchType.PURCHASE_RETURN),
        int(VchType.MATERIAL_ISSUE),
        int(VchType.PHYSICAL_STOCK),
    }
)


@dataclass(frozen=True)
class StockMovement:
    vch_code: int
    vch_type: int
    rec_type: int
    qty: Decimal


async def fetch_item_stock_movements(client: BusyClient, item_code: int) -> list[StockMovement]:
    """SC=1 — pull every Tran2 line for one item. Not paginated: PRD §11's pagination
    concern is about bulk entity syncs (every item, every row); one item's own
    transaction history is expected to stay small even at retail scale."""
    xml = await client.run_query(
        f"SELECT VchCode, VchType, RecType, Value1 FROM Tran2 WHERE MasterCode1 = {item_code}"
    )
    rows = parse_rowset_xml(xml)
    return [
        StockMovement(
            vch_code=int(row["VchCode"]),
            vch_type=int(row["VchType"]),
            rec_type=int(row["RecType"]),
            qty=Decimal(row["Value1"]),
        )
        for row in rows
    ]


def compute_item_stock(movements: list[StockMovement]) -> Decimal:
    """Sums signed Qty across every real stock-moving transaction line for one item.
    UNVERIFIED — see module docstring."""
    total = Decimal("0")
    for m in movements:
        if m.rec_type != ITEM_MOVEMENT_REC_TYPE:
            continue
        if m.vch_type not in STOCK_MOVING_VCH_TYPES:
            continue
        total += m.qty
    return total
