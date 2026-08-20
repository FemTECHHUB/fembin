"""Read-side of the catalog domain — API route handlers call these, never BUSY or the ORM
directly (CLAUDE.md §2.1). Always reads MySQL; never triggers a BUSY call."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category, MaterialCenter, Product, Salesman, SyncState


class ProductNotFoundError(Exception):
    """Raised when a busy_code doesn't match any product in our mirror."""


class DuplicateBarcodeError(Exception):
    """Raised when a barcode is already assigned to a different product."""


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


def set_product_barcode(session: Session, code: int, barcode: str) -> Product:
    """Assign a barcode to a product — local-only (CLAUDE.md §8: this company's real Item
    master has no barcode data). Catalog sync never touches this column, so it survives
    every re-sync."""
    product = session.get(Product, code)
    if product is None:
        raise ProductNotFoundError(code)

    existing = session.scalar(
        select(Product).where(Product.barcode == barcode, Product.busy_code != code)
    )
    if existing is not None:
        raise DuplicateBarcodeError(barcode)

    product.barcode = barcode
    session.commit()
    session.refresh(product)
    return product


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.busy_group_name)))


def list_material_centers(session: Session) -> list[MaterialCenter]:
    return list(session.scalars(select(MaterialCenter).order_by(MaterialCenter.name)))


def list_salesmen(session: Session, *, active_only: bool = True) -> list[Salesman]:
    """BUSY's Executive master (MasterType=33), synced read-only — see Salesman's
    docstring for why this isn't something we create/edit locally."""
    stmt = select(Salesman)
    if active_only:
        stmt = stmt.where(Salesman.is_active.is_(True))
    return list(session.scalars(stmt.order_by(Salesman.name)))


def get_salesman(session: Session, code: int) -> Salesman | None:
    return session.get(Salesman, code)


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
