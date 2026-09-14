"""app/domain/catalog/vch_series.py — resolving each branch's real BUSY voucher series
and numbering prefix from its own transaction history, never a hardcoded mapping."""

from sqlalchemy.orm import Session

from app.busy.client import BusyClient
from app.db.models import MaterialCenter
from app.domain.catalog.vch_series import (
    VchSeriesUnresolvedError,
    resolve_vch_series,
    sync_vch_series,
)


async def test_resolve_vch_series_ignores_non_quotation_voucher_types(
    busy_client: BusyClient,
) -> None:
    """Material center 201 has a fake Sale (VchType=9) voucher with a *higher* VchCode
    than either of its two real Sale Quotations (VchType=26) — if the VchType filter
    weren't actually applied, the Sale would win and resolve to the wrong series
    entirely (confirmed live 2026-09-07: a branch's Sale and Sale Quotation series can
    be completely different). Must resolve using only the Sale Quotation rows."""
    series_name, prefix = await resolve_vch_series(busy_client, 201)
    assert series_name == "Main"
    assert prefix == "RCC"


async def test_resolve_vch_series_picks_the_majority_series_not_the_most_recent(
    busy_client: BusyClient,
) -> None:
    """Material center 1155 has two *active* Sale Quotation series — 302 used 3 times,
    305 used once — modeled directly on a real branch found to split quotations this
    way (module docstring). Must resolve to the majority series (302 -> "JCT"), not
    whichever has the highest VchCode (which could be either, depending on which was
    posted most recently on any given day)."""
    series_name, prefix = await resolve_vch_series(busy_client, 1155)
    assert series_name == "RC Taiwo"
    assert prefix == "JCT"


async def test_resolve_vch_series_raises_when_branch_has_no_voucher_history(
    busy_client: BusyClient,
) -> None:
    """A genuinely new branch that's never had a voucher posted — no safe way to guess,
    must raise rather than silently fall back to something wrong."""
    try:
        await resolve_vch_series(busy_client, 555)
        raise AssertionError("expected VchSeriesUnresolvedError")
    except VchSeriesUnresolvedError as exc:
        assert "no Sale Quotation history" in str(exc)


async def test_resolve_vch_series_raises_when_only_sale_history_exists(
    busy_client: BusyClient,
) -> None:
    """Material center 777 has real Sale (VchType=9) history but has never had a Sale
    Quotation posted — must still be treated as unresolved for quotation purposes,
    proving this isn't just "has some voucher history," it specifically means Sale
    Quotation history."""
    try:
        await resolve_vch_series(busy_client, 777)
        raise AssertionError("expected VchSeriesUnresolvedError")
    except VchSeriesUnresolvedError as exc:
        assert "no Sale Quotation history" in str(exc)


async def test_resolve_vch_series_raises_when_series_code_not_in_master(
    busy_client: BusyClient,
) -> None:
    """Material center 9999's only voucher references series code 303, which the fake
    Voucher Series master deliberately doesn't include — must raise, not silently use
    an empty/unknown series name."""
    try:
        await resolve_vch_series(busy_client, 9999)
        raise AssertionError("expected VchSeriesUnresolvedError")
    except VchSeriesUnresolvedError as exc:
        assert "not found" in str(exc)


async def test_sync_vch_series_resolves_unresolved_material_centers(
    db_session: Session, busy_client: BusyClient
) -> None:
    mc = MaterialCenter(busy_code=201, name="Main Store", is_active=True)
    db_session.add(mc)
    db_session.commit()

    await sync_vch_series(db_session, busy_client)

    db_session.refresh(mc)
    assert mc.vch_series_name == "Main"
    assert mc.vch_no_prefix == "RCC"
    assert mc.vch_series_resolved_at is not None


async def test_sync_vch_series_never_touches_an_already_resolved_branch(
    db_session: Session, busy_client: BusyClient
) -> None:
    """Resolution is a one-time thing (CLAUDE.md — this doesn't change once BUSY is set
    up) — an already-resolved branch must be left exactly as-is, not re-queried."""
    mc = MaterialCenter(
        busy_code=201,
        name="Main Store",
        is_active=True,
        vch_series_name="Some Other Series",
        vch_no_prefix="XYZ",
    )
    db_session.add(mc)
    db_session.commit()

    await sync_vch_series(db_session, busy_client)

    db_session.refresh(mc)
    assert mc.vch_series_name == "Some Other Series"
    assert mc.vch_no_prefix == "XYZ"


async def test_sync_vch_series_leaves_unresolvable_branch_alone_without_raising(
    db_session: Session, busy_client: BusyClient
) -> None:
    """A branch with no BUSY voucher history yet must not crash the whole sync pass —
    it's just left unresolved (and thus unable to take quotations, see
    app/api/v1/quotations.py) until it has real history to derive from."""
    mc = MaterialCenter(busy_code=555, name="Brand New Branch", is_active=True)
    db_session.add(mc)
    db_session.commit()

    await sync_vch_series(db_session, busy_client)  # must not raise

    db_session.refresh(mc)
    assert mc.vch_series_name is None
    assert mc.vch_no_prefix is None
