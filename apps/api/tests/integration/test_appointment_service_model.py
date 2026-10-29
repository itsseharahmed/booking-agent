"""Integration tests for appointment service storage."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic


def test_global_appointment_duration() -> None:
    assert APPOINTMENT_DURATION_MINUTES == 20


def test_create_service(test_session: Session) -> None:
    service = AppointmentService(
        name="Comprehensive Eye Exam",
        description="Routine eye examination",
    )

    test_session.add(service)
    test_session.flush()
    test_session.refresh(service)

    assert service.id is not None
    assert service.is_active is True


def test_service_can_be_deactivated(test_session: Session) -> None:
    service = AppointmentService(
        name="Contact Lens Assessment",
    )

    test_session.add(service)
    test_session.flush()

    service.is_active = False
    test_session.flush()
    test_session.refresh(service)

    assert service.is_active is False


def test_duplicate_service_name_rejected(
    test_session: Session,
) -> None:
    test_session.add(AppointmentService(name="Eye Exam"))
    test_session.flush()

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(AppointmentService(name="Eye Exam"))
        test_session.flush()


def test_clinic_specific_appointment_price(
    test_session: Session,
) -> None:
    clinic = Clinic(
        name="Price Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("120.00"),
    )

    test_session.add(clinic)
    test_session.flush()
    test_session.refresh(clinic)

    assert clinic.appointment_price == Decimal("120.00")


def test_negative_clinic_price_rejected(
    test_session: Session,
) -> None:
    clinic = Clinic(
        name="Invalid Price Clinic",
        address_line1="456 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("-1.00"),
    )

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(clinic)
        test_session.flush()


def test_different_clinics_can_have_different_prices(
    test_session: Session,
) -> None:
    first = Clinic(
        name="First Pricing Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("100.00"),
    )

    second = Clinic(
        name="Second Pricing Clinic",
        address_line1="456 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("130.00"),
    )

    test_session.add_all([first, second])
    test_session.flush()

    assert first.appointment_price != second.appointment_price
