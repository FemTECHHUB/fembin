"""Resolves each Material Center's real BUSY Voucher Series and numbering prefix —
never hardcoded, always read from the branch's own transaction history.

BUSY numbers each voucher series independently, with its own prefix (e.g. series
"Main" -> "RCC-<n>"), and there is no clean field for the prefix anywhere in BUSY's
schema (CLAUDE.md §8 / app/busy/vch_numbering.py) — it's a human naming convention,
only visible in real posted VchNo values. This module derives it automatically per
branch from that branch's own real voucher history, rather than a hardcoded or
manually-typed mapping — required for this to keep working unattended as branches are
added, and to work unmodified against a different BUSY installation entirely.

KNOWN LIMITATION (v1, flagged 2026-09-07, not yet resolved): a single branch can
legitimately run more than one Sale Quotation series for different visit types —
confirmed live on Repair Centre Taiwo, which runs a general "Job Card" series (JCT)
*and* a separate "Diagnosis" series (RTD) for diagnosis-only visits, both currently
active. This module resolves to whichever series a branch uses most (its general-
purpose one) and has no way yet to route a diagnosis-only cart to the Diagnosis series
specifically — that cart currently gets filed under the branch's general series
instead. There's also a Sale Type master (MasterType=13) that may need accounting for
alongside this. Deliberately deferred rather than guessed at without the real target
BUSY installation's data in front of us — revisit before relying on this for a branch
known to split quotations this way.
"""

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.busy.constants import VchType
from app.busy.xml_util import parse_rowset_xml
from app.db.models import MaterialCenter

logger = logging.getLogger(__name__)

_VCH_NO_PATTERN = re.compile(r"^(.*)-(\d+)\s*$")


class VchSeriesUnresolvedError(Exception):
    """Raised when a material center has no BUSY voucher history to derive its series
    from yet — a genuinely new branch that's never had a voucher posted. Needs one
    voucher posted for it (BUSY GUI or otherwise) before this can resolve; there is no
    safe way to guess a series/prefix with zero real data to read it from."""


async def resolve_vch_series(client: BusyClient, material_center_code: int) -> tuple[str, str]:
    """Reads (series_name, prefix) off this branch's real Sale Quotation history — the
    same ground truth a human would otherwise have to read off the BUSY GUI by hand,
    just automated. Two BUSY calls: one finds every quotation for this branch, one
    resolves the winning series code to its human-readable name (MasterType=21,
    "Voucher Series").

    Filtering by VchType matters, confirmed live 2026-09-07: a branch's *Sale*
    vouchers (VchType=9) and *Sale Quotation* vouchers (VchType=26) use entirely
    different series — Repair Centre Taiwo's Sale Quotations use prefix "JCT", its
    Sales use "JRT". An earlier version of this function didn't filter by VchType and
    picked up whichever voucher had the highest VchCode regardless of type, silently
    returning the wrong prefix for what this system actually posts (quotations).

    Resolves to the branch's *most-used* series among its Sale Quotations, not simply
    the most recent one — also confirmed live 2026-09-07: a branch can legitimately run
    more than one active Sale Quotation series concurrently (see module docstring,
    Repair Centre Taiwo's JCT/RTD split). "Most recent" is unreliable there since the
    two interleave day to day; the highest-volume series reliably identifies the
    branch's general-purpose one without needing to know anything company-specific
    about what the other series is for."""
    xml = await client.run_query(
        "SELECT VchCode, VchSeriesCode, VchNo FROM Tran1 "
        f"WHERE MasterCode2 = {material_center_code} "
        f"AND VchType = {int(VchType.SALE_QUOTATION)}"
    )
    rows = parse_rowset_xml(xml)
    if not rows:
        raise VchSeriesUnresolvedError(
            f"material center {material_center_code} has no Sale Quotation history "
            "in BUSY yet — post at least one Sale Quotation for this branch before it "
            "can take Sale Quotations through this system"
        )

    counts: dict[str, int] = {}
    for row in rows:
        code = row.get("VchSeriesCode", "").strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    winning_series_code = max(counts, key=lambda code: counts[code])
    candidates = [r for r in rows if r.get("VchSeriesCode", "").strip() == winning_series_code]
    most_recent = max(candidates, key=lambda r: int(r.get("VchCode", "0") or "0"))

    series_code = most_recent.get("VchSeriesCode", "").strip()
    vch_no = most_recent.get("VchNo", "").strip()
    match = _VCH_NO_PATTERN.match(vch_no)
    if not series_code or not match:
        raise VchSeriesUnresolvedError(
            f"material center {material_center_code}: most recent voucher {vch_no!r} "
            f"(series code {series_code!r}) doesn't match the expected '<prefix>-<n>' "
            "pattern — cannot safely derive a prefix from it"
        )
    prefix = match.group(1)

    xml2 = await client.run_query(
        f"SELECT Code, Name FROM Master1 WHERE MasterType = 21 AND Code = {series_code}"
    )
    series_rows = parse_rowset_xml(xml2)
    # Verify identity explicitly rather than trusting the WHERE clause + row order
    # alone — a defensive check, not a formality: it's what caught a real bug in this
    # function's own test double (tests/fixtures/mock_busy.py originally ignored the
    # Code filter entirely and returned every series regardless).
    matching = [r for r in series_rows if r.get("Code", "").strip() == series_code]
    series_name = matching[0].get("Name", "").strip() if matching else ""
    if not series_name:
        raise VchSeriesUnresolvedError(
            f"material center {material_center_code}: voucher series code "
            f"{series_code!r} not found (or unnamed) in BUSY's Voucher Series master"
        )

    return series_name, prefix


async def sync_vch_series(session: Session, client: BusyClient) -> None:
    """Resolves every active material center that doesn't have a resolved series yet.
    Best-effort per branch — one branch failing to resolve (e.g. genuinely no history
    yet) never blocks the others, and never blocks the rest of catalog sync (called
    from app/domain/catalog/scheduler.py, after material centers are synced). Never
    re-resolves an already-resolved branch — this doesn't change once BUSY is set up,
    so there's no reason to spend BUSY calls re-checking it on every pass."""
    unresolved = list(
        session.scalars(
            select(MaterialCenter).where(
                MaterialCenter.is_active.is_(True),
                MaterialCenter.vch_series_name.is_(None),
            )
        )
    )
    for material_center in unresolved:
        try:
            series_name, prefix = await resolve_vch_series(client, material_center.busy_code)
        except VchSeriesUnresolvedError as exc:
            logger.warning(
                "material center %s (%s): voucher series still unresolved: %s",
                material_center.busy_code,
                material_center.name,
                exc,
            )
            continue
        material_center.vch_series_name = series_name
        material_center.vch_no_prefix = prefix
        material_center.vch_series_resolved_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        logger.info(
            "material center %s (%s): resolved voucher series=%r prefix=%r",
            material_center.busy_code,
            material_center.name,
            series_name,
            prefix,
        )
