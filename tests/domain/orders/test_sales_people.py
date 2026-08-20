"""app/domain/orders/sales_people.py."""

import pytest
from sqlalchemy.orm import Session

from app.db.models import MaterialCenter
from app.domain.orders.sales_people import (
    SalesPersonNotFoundError,
    UnknownMaterialCenterError,
    create_sales_person,
    list_sales_people,
    reassign_sales_person,
)


def test_create_sales_person_ties_to_a_real_material_center(
    db_session: Session, material_center: MaterialCenter
) -> None:
    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )

    assert person.id is not None
    assert person.material_center_code == material_center.busy_code
    assert person.is_active is True


def test_create_sales_person_rejects_unknown_material_center(db_session: Session) -> None:
    with pytest.raises(UnknownMaterialCenterError):
        create_sales_person(db_session, full_name="Ghost", material_center_code=999999)


def test_list_sales_people_scoped_to_material_center(db_session: Session) -> None:
    mc1 = MaterialCenter(busy_code=201, name="Main Store", is_active=True)
    mc2 = MaterialCenter(busy_code=1155, name="Repair Centre Taiwo", is_active=True)
    db_session.add_all([mc1, mc2])
    db_session.commit()

    create_sales_person(db_session, full_name="Femi Sales", material_center_code=201)
    create_sales_person(db_session, full_name="Chidi Sales", material_center_code=1155)

    scoped = list_sales_people(db_session, material_center_code=201)
    assert [p.full_name for p in scoped] == ["Femi Sales"]

    unscoped = list_sales_people(db_session)
    assert {p.full_name for p in unscoped} == {"Femi Sales", "Chidi Sales"}


def test_list_sales_people_excludes_inactive_by_default(
    db_session: Session, material_center: MaterialCenter
) -> None:
    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )
    reassign_sales_person(db_session, person.id, is_active=False)

    assert list_sales_people(db_session, material_center_code=material_center.busy_code) == []
    assert len(list_sales_people(db_session, active_only=False)) == 1


def test_reassign_sales_person_moves_branch(
    db_session: Session, material_center: MaterialCenter
) -> None:
    other_center = MaterialCenter(busy_code=1155, name="Repair Centre Taiwo", is_active=True)
    db_session.add(other_center)
    db_session.commit()

    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )
    moved = reassign_sales_person(db_session, person.id, material_center_code=1155)

    assert moved.material_center_code == 1155


def test_reassign_sales_person_rejects_unknown_material_center(
    db_session: Session, material_center: MaterialCenter
) -> None:
    person = create_sales_person(
        db_session, full_name="Femi Sales", material_center_code=material_center.busy_code
    )
    with pytest.raises(UnknownMaterialCenterError):
        reassign_sales_person(db_session, person.id, material_center_code=999999)


def test_reassign_sales_person_rejects_unknown_id(db_session: Session) -> None:
    with pytest.raises(SalesPersonNotFoundError):
        reassign_sales_person(db_session, 999999, is_active=False)
