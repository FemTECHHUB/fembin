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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
