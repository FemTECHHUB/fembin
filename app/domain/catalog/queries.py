"""Read-side of the catalog domain — API route handlers call these, never BUSY or the ORM
directly (CLAUDE.md §2.1). Always reads MySQL; never triggers a BUSY call."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category, MaterialCenter, Product, SyncState


def list_products(
    session: Session,
    *,
    search: str | None = None,
    category: str | None = None,
    active: bool | None = None,
) -> list[Product]:
    stmt = select(Product)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    if category:
        stmt = stmt.where(Product.item_group == category)
    if active is not None:
        stmt = stmt.where(Product.is_active == active)
    stmt = stmt.order_by(Product.name)
    return list(session.scalars(stmt))


def get_product(session: Session, code: int) -> Product | None:
    return session.get(Product, code)


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.busy_group_name)))


def list_material_centers(session: Session) -> list[MaterialCenter]:
    return list(session.scalars(select(MaterialCenter).order_by(MaterialCenter.name)))


@dataclass(frozen=True)
class SyncStatusEntry:
    entity: str
    last_stamp: int
    updated_at: datetime


def get_sync_status(session: Session) -> list[SyncStatusEntry]:
    rows = session.scalars(select(SyncState).order_by(SyncState.entity))
    return [
        SyncStatusEntry(entity=r.entity, last_stamp=r.last_stamp, updated_at=r.updated_at)
        for r in rows
    ]
