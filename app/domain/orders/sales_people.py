"""Sales people — named individuals credited on a Sale Quotation, distinct from `User`
logins (see app/db/models.py's `SalesPerson` docstring for why). Local-only master data,
not synced from or pushed to BUSY."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter, SalesPerson


class UnknownMaterialCenterError(Exception):
    """Raised when the given material center code doesn't exist in our mirror, or is
    inactive — a sales person must be tied to a real, currently-active branch."""


class SalesPersonNotFoundError(Exception):
    """Raised when a sales_person_id doesn't exist."""


def create_sales_person(
    session: Session, *, full_name: str, material_center_code: int
) -> SalesPerson:
    material_center = session.get(MaterialCenter, material_center_code)
    if material_center is None or not material_center.is_active:
        raise UnknownMaterialCenterError(material_center_code)

    person = SalesPerson(full_name=full_name, material_center_code=material_center_code)
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def list_sales_people(
    session: Session, *, material_center_code: int | None = None, active_only: bool = True
) -> list[SalesPerson]:
    """Every sales person, optionally scoped to one branch — used both for a user's own
    "pick your name" dropdown (scoped) and the superadmin dashboard (unscoped)."""
    stmt = select(SalesPerson)
    if material_center_code is not None:
        stmt = stmt.where(SalesPerson.material_center_code == material_center_code)
    if active_only:
        stmt = stmt.where(SalesPerson.is_active.is_(True))
    stmt = stmt.order_by(SalesPerson.full_name)
    return list(session.scalars(stmt))


def reassign_sales_person(
    session: Session,
    sales_person_id: int,
    *,
    material_center_code: int | None = None,
    is_active: bool | None = None,
) -> SalesPerson:
    """Superadmin-only edit (CLAUDE.md NFR6 follow-up, explicit request 2026-08-20): move a
    sales person to a different branch, or (de)activate them, without deleting history —
    existing quotations already carry the sales person's name/id in their own payload."""
    person = session.get(SalesPerson, sales_person_id)
    if person is None:
        raise SalesPersonNotFoundError(sales_person_id)

    if material_center_code is not None:
        material_center = session.get(MaterialCenter, material_center_code)
        if material_center is None or not material_center.is_active:
            raise UnknownMaterialCenterError(material_center_code)
        person.material_center_code = material_center_code

    if is_active is not None:
        person.is_active = is_active

    session.commit()
    session.refresh(person)
    return person
