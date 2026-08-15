"""Voucher-number computation for BUSY companies with Detailed Audit Trail enabled.

Confirmed live 2026-08-15 against the BUSY test company (CLAUDE.md §8 has the full
writeup): posting a voucher with an arbitrary or omitted `VchNo` is rejected —
`"Voucher number can not be blank"` — once Detailed Audit Trail is on. Each voucher
*series* numbers independently with its own prefix (e.g. series "Main" produces
"RCC-<n>", confirmed by inspecting real data — not derivable from BUSY, not documented
anywhere, so the caller must know and supply the prefix for their series).
"""

import re

from app.busy.client import BusyClient
from app.busy.xml_util import parse_rowset_xml


def _vch_no_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(prefix)}-(\d+)$")


async def get_next_vch_no(client: BusyClient, vch_type: int, prefix: str) -> str:
    """Finds the highest existing "<prefix>-<n>" VchNo for this voucher type and
    returns the next one. Starts at "<prefix>-1" if the prefix has never been used.

    `VchNo` is stored left-padded/fixed-width — `LTRIM` is required in the query or
    this never matches (confirmed live: a plain `WHERE VchNo='...'` returned 0 rows
    for a voucher proven to exist by VchCode lookup)."""
    xml = await client.run_query(
        f"SELECT VchNo FROM Tran1 WHERE VchType={vch_type} AND LTRIM(VchNo) LIKE '{prefix}-%'"
    )
    rows = parse_rowset_xml(xml)
    pattern = _vch_no_pattern(prefix)
    max_n = 0
    for row in rows:
        match = pattern.match(row.get("VchNo", "").strip())
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"{prefix}-{max_n + 1}"
