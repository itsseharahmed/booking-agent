"""Database integrity tests for appointment bookings."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic


@pytest.fixture
def booking_data(test_session: Session):
    clinic = Clinic(
        name="Booking Model Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("120.00"),
    )

    optometrist = Optometrist(
        first_name="Booking",
        last_name="Tester",
    )

    service = AppointmentService(
        name="Booking Model Eye Exam",
    )

    test_session.add_all([clinic, optometrist, service])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    return clinic, optometrist, service


def make_appointment(
    booking_data,
    *,
    start: datetime | None = None,
    status: str = "booked",
) -> Appointment:
    clinic, optometrist, service = booking_data

    start = start or datetime(2026, 11, 2, 14, 0, tzinfo=UTC)

    return Appointment(
        clinic_id=clinic.id,
        optometrist_id=optometrist.id,
        service_id=service.id,
        start_at=start,
        end_at=start + timedelta(minutes=20),
        status=status,
        appointment_price=Decimal("120.00"),
        cancelled_at=(datetime.now(UTC) if status == "cancelled" else None),
    )


def test_same_optometrist_cannot_overlap_across_clinics(test_session, booking_data):
    _, optometrist, service = booking_data

    second_clinic = Clinic(
        name="Second Booking Test Clinic",
        address_line1="456 King Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 1K4",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("140.00"),
    )
    test_session.add(second_clinic)
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=second_clinic.id,
        )
    )
    test_session.flush()

    first = make_appointment(booking_data)
    test_session.add(first)
    test_session.flush()

    second = Appointment(
        clinic_id=second_clinic.id,
        optometrist_id=optometrist.id,
        service_id=service.id,
        start_at=first.start_at + timedelta(minutes=10),
        end_at=first.end_at + timedelta(minutes=10),
        status="booked",
        appointment_price=Decimal("140.00"),
    )

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(second)
        test_session.flush()


def test_create_appointment(test_session, booking_data):
    appointment = make_appointment(booking_data)
    test_session.add(appointment)
    test_session.flush()

    assert appointment.id is not None
    assert appointment.status == "booked"


def test_overlapping_appointments_rejected(test_session, booking_data):
    first = make_appointment(booking_data)
    test_session.add(first)
    test_session.flush()

    overlapping = make_appointment(
        booking_data,
        start=first.start_at + timedelta(minutes=10),
    )

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(overlapping)
        test_session.flush()


def test_adjacent_appointments_allowed(test_session, booking_data):
    first = make_appointment(booking_data)
    second = make_appointment(
        booking_data,
        start=first.start_at + timedelta(minutes=20),
    )

    test_session.add_all([first, second])
    test_session.flush()

    assert first.id != second.id


def test_cancelled_appointment_releases_slot(test_session, booking_data):
    cancelled = make_appointment(
        booking_data,
        status="cancelled",
    )
    replacement = make_appointment(booking_data)

    test_session.add_all([cancelled, replacement])
    test_session.flush()

    assert replacement.id is not None


def test_invalid_duration_rejected(test_session, booking_data):
    appointment = make_appointment(booking_data)
    appointment.end_at = appointment.start_at + timedelta(minutes=30)

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(appointment)
        test_session.flush()


def test_negative_price_rejected(test_session, booking_data):
    appointment = make_appointment(booking_data)
    appointment.appointment_price = Decimal("-1.00")

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(appointment)
        test_session.flush()


def test_invalid_status_rejected(test_session, booking_data):
    appointment = make_appointment(
        booking_data,
        status="invalid",
    )

    with pytest.raises(IntegrityError), test_session.begin_nested():
        test_session.add(appointment)
        test_session.flush()
