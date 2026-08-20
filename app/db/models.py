"""ORM models — our MySQL mirror of BUSY masters, per PRD §5's data model.

Blocked/deactivated BUSY records are reflected as `is_active = False` here, never deleted
(CLAUDE.md §2.4) — a real bug in the Node prototype was filtering inactive records out
*before* storage, which meant a newly-blocked record silently never updated once
incremental sync replaced full re-pulls.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SyncState(Base):
    """One row per synced entity — the incremental-sync checkpoint (CLAUDE.md §2.3).
    `last_stamp` only ever advances after a successful write to our own tables."""

    __tablename__ = "sync_state"

    entity: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_stamp: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MaterialCenter(Base):
    """A BUSY Material Center (MasterType=11) — a store/warehouse/branch."""

    __tablename__ = "material_centers"

    busy_code: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    alias: Mapped[str | None] = mapped_column(String(64), default=None)
    parent_group: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Category(Base):
    """Derived from the distinct `ParentGroup` values seen on active Items — BUSY's
    Item Group master (MasterType=5) isn't synced separately this sprint (PRD §5)."""

    __tablename__ = "categories"

    busy_group_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    woo_category_id: Mapped[int | None] = mapped_column(default=None)


class Product(Base):
    """A BUSY Item (MasterType=6). Stock is deliberately not a column here — it isn't
    on the Item master and deriving it from transactions is unsolved (PRD §5 non-goal)."""

    __tablename__ = "products"

    busy_code: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(64), default="")
    item_group: Mapped[str] = mapped_column(
        String(255), ForeignKey("categories.busy_group_name"), default="Uncategorised"
    )
    tracks_stock: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    woo_product_id: Mapped[int | None] = mapped_column(default=None)
    # The price value last successfully pushed to WooCommerce — compared against `price`
    # to decide whether a live update is needed, independent of BUSY's Stamp (Sprint 2).
    woo_synced_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    # Locally-owned, NOT synced from BUSY — live-checked 2026-08-20 (CLAUDE.md §8): this
    # company's real Item master has no barcode data anywhere (PrintName just mirrors
    # Name). Catalog sync (app/domain/catalog/sync.py) must never overwrite this field.
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    """An app login — a rep or cashier at a real branch. Every user is tied to exactly one
    `MaterialCenter` (CLAUDE.md NFR6 / PRD §6): every action they take (creating a
    quotation, eventually a sale) is scoped to that material center rather than left as
    free-text input, so BUSY vouchers and our own records reflect a real identity instead
    of only ever showing the shared BUSY service account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    material_center_code: Mapped[int] = mapped_column(ForeignKey("material_centers.busy_code"))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Can create/manage users and sales people, and see every material center's data
    # (superadmin dashboard) rather than being scoped to just one branch.
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Salesman(Base):
    """A BUSY Executive (MasterType=33) — "Salesmen" in BUSY's own terminology. A named
    individual credited on a Sale Quotation, distinct from `User`: several people may
    share one till/login at a branch, but each sale should still be attributable to
    whoever actually made it (CLAUDE.md NFR6).

    Corrected 2026-08-20: this was first built as a table we owned and let callers create
    entries into (`sales_people`) — wrong. BUSY already has a real master for this
    (confirmed in the research phase, docs/reference/14-command-center.md), so it must be
    synced read-only like Product/MaterialCenter, never created/edited from our side.
    Whether BUSY ties an Executive to a specific Material Center is unconfirmed — the
    generic Master1 schema shows no such field, so no branch-scoping is applied here
    (CLAUDE.md §8)."""

    __tablename__ = "salesmen"

    busy_code: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    alias: Mapped[str | None] = mapped_column(String(64), default=None)
    parent_group: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WooSyncState(Base):
    """Singleton row (id=1) — the WooCommerce push's own state, separate from the BUSY-side
    `sync_state` checkpoints: the one-time seed-import opt-in (CLAUDE.md-style deliberate
    safety net, ported from the prototype's `state.json.seeded`) and the last push result,
    for `GET /api/v1/sync/status` to show."""

    __tablename__ = "woo_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    seeded: Mapped[bool] = mapped_column(default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    last_seeded: Mapped[int] = mapped_column(default=0)
    last_created: Mapped[int] = mapped_column(default=0)
    last_updated: Mapped[int] = mapped_column(default=0)
    last_skipped: Mapped[int] = mapped_column(default=0)
    last_failed: Mapped[int] = mapped_column(default=0)
