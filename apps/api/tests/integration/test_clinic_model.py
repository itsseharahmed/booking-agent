"""Integration tests for the Clinic database model."""

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic


def test_clinics_table_exists(test_engine: Engine) -> None:
    """The database should contain a clinics table."""
    inspector = inspect(test_engine)

    assert "clinics" in inspector.get_table_names()


def test_clinics_table_has_required_columns(test_engine: Engine) -> None:
    """The clinics table should contain the expected fields."""
    inspector = inspect(test_engine)

    columns = {column["name"] for column in inspector.get_columns("clinics")}

    expected_columns = {
        "id",
        "name",
        "address_line1",
        "address_line2",
        "city",
        "province",
        "postal_code",
        "country",
        "phone",
        "timezone",
        "is_active",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(columns)


def test_create_clinic(test_session: Session) -> None:
    """A clinic can be saved to the test database."""
    clinic = Clinic(
        name="Downtown Vision Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(clinic)
    test_session.flush()
    test_session.refresh(clinic)

    assert clinic.id is not None
    assert clinic.name == "Downtown Vision Clinic"
    assert clinic.is_active is True
    assert clinic.created_at is not None
    assert clinic.updated_at is not None


def test_retrieve_clinic(test_session: Session) -> None:
    """A saved clinic can be retrieved by its ID."""
    clinic = Clinic(
        name="North York Vision Clinic",
        address_line1="456 Yonge Street",
        city="Toronto",
        province="Ontario",
        postal_code="M2N 5P6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(clinic)
    test_session.flush()

    saved_clinic = test_session.scalar(select(Clinic).where(Clinic.id == clinic.id))

    assert saved_clinic is not None
    assert saved_clinic.id == clinic.id
    assert saved_clinic.name == "North York Vision Clinic"
    assert saved_clinic.city == "Toronto"


def test_database_rejects_non_toronto_timezone(
    test_session: Session,
) -> None:
    """PostgreSQL must reject clinics outside America/Toronto."""

    clinic = Clinic(
        name="Unsupported Timezone Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Vancouver",
    )

    test_session.add(clinic)

    with pytest.raises(IntegrityError):
        test_session.flush()
