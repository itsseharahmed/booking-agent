"""Patient database integrity tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.db.models.patient import Patient


def make_patient(
    *,
    email: str = "patient@example.com",
) -> Patient:
    return Patient(
        first_name="Test",
        last_name="Patient",
        email=email,
        password_hash="test-only-placeholder-not-a-real-hash",
    )


def test_create_patient(test_session: Session) -> None:
    patient = make_patient()
    test_session.add(patient)
    test_session.flush()

    assert patient.id is not None
    assert patient.email == "patient@example.com"
    assert patient.is_active is True


def test_patient_email_case_insensitive_unique(
    test_session: Session,
) -> None:
    first = make_patient(email="Patient@Example.com")
    test_session.add(first)
    test_session.flush()

    second = make_patient(email="patient@example.com")

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(second)
        test_session.flush()


def test_multiple_patients_allowed(
    test_session: Session,
) -> None:
    first = make_patient(email="first@example.com")
    second = make_patient(email="second@example.com")

    test_session.add_all([first, second])
    test_session.flush()

    assert first.id != second.id


def test_patient_can_be_deactivated(
    test_session: Session,
) -> None:
    patient = make_patient()
    test_session.add(patient)
    test_session.flush()

    patient.is_active = False
    test_session.flush()

    stored = test_session.scalar(select(Patient).where(Patient.id == patient.id))

    assert stored is not None
    assert stored.is_active is False


def test_patient_password_hash_required(
    test_session: Session,
) -> None:
    patient = make_patient()
    patient.password_hash = None  # type: ignore[assignment]

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(patient)
        test_session.flush()
