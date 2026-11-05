"""PostgreSQL tests for confirmed booking price protection."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import optometry.booking.service as booking_service
from optometry.availability.service import get_availability
from optometry.booking.service import create_appointment
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.patient import Patient
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.schemas.appointment import AppointmentCreate


# checks the approved price remains protected during concurrent updates
def test_confirmed_booking_locks_clinic_price(
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    suffix = uuid4().hex[:12]

    # create committed test records visible to independent connections
    with session_factory() as db:
        clinic = Clinic(
            name=f"Price Lock Clinic {suffix}",
            address_line1="123 Main Street",
            city="Toronto",
            province="Ontario",
            postal_code="M5V 2T6",
            country="CA",
            timezone="America/Toronto",
            appointment_price=Decimal("95.00"),
        )
        doctor = Optometrist(
            first_name="Price",
            last_name="Lock",
        )
        service = AppointmentService(
            name=f"Price Lock Exam {suffix}",
        )
        patient = Patient(
            first_name="Price",
            last_name="Patient",
            email=f"price-lock-{suffix}@example.com",
            password_hash="test-hash",
        )

        db.add_all([clinic, doctor, service, patient])
        db.flush()

        clinic_id = clinic.id
        doctor_id = doctor.id
        service_id = service.id
        patient_id = patient.id

        db.add(
            OptometristClinic(
                clinic_id=clinic_id,
                optometrist_id=doctor_id,
            )
        )

        target = datetime.now(UTC).date() + timedelta(days=21)
        target += timedelta(days=(0 - target.weekday()) % 7)

        db.add(
            WorkingSchedule(
                clinic_id=clinic_id,
                optometrist_id=doctor_id,
                day_of_week=0,
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("10:00", "%H:%M").time(),
                is_active=True,
            )
        )
        db.commit()

    booking_locked = Event()
    release_booking = Event()

    try:
        # select a real available appointment slot
        with session_factory() as db:
            price, slots = get_availability(
                db=db,
                clinic_id=clinic_id,
                optometrist_id=doctor_id,
                service_id=service_id,
                appointment_date=target,
                now=datetime.now(UTC),
            )

            assert price == Decimal("95.00")
            assert slots

            start_at = slots[0].start

        payload = AppointmentCreate(
            clinic_id=clinic_id,
            optometrist_id=doctor_id,
            service_id=service_id,
            start_at=start_at,
        )

        original_availability = booking_service.get_availability

        # pause after the booking service acquires its clinic lock
        def paused_availability(**kwargs):
            booking_locked.set()

            if not release_booking.wait(timeout=10):
                raise RuntimeError("Booking concurrency test timed out")

            return original_availability(**kwargs)

        monkeypatch.setattr(
            booking_service,
            "get_availability",
            paused_availability,
        )

        def book() -> int:
            with session_factory() as db:
                appointment = create_appointment(
                    db,
                    payload,
                    patient_id=patient_id,
                    now=datetime.now(UTC),
                    expected_price=Decimal("95.00"),
                )
                return appointment.id

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(book)

            try:
                assert booking_locked.wait(timeout=10)

                # the administrator must not change the price
                # while the booking holds the clinic row lock
                with session_factory() as admin_db:
                    admin_db.execute(text("SET LOCAL lock_timeout = '300ms'"))

                    with pytest.raises(OperationalError):
                        admin_db.execute(
                            update(Clinic)
                            .where(Clinic.id == clinic_id)
                            .values(appointment_price=Decimal("110.00"))
                        )

                    admin_db.rollback()
            finally:
                release_booking.set()

            appointment_id = future.result(timeout=15)

        # the booking committed at the exact approved price
        with session_factory() as db:
            appointment = db.get(Appointment, appointment_id)
            assert appointment is not None
            assert appointment.status == "booked"
            assert appointment.appointment_price == Decimal("95.00")

            clinic = db.get(Clinic, clinic_id)
            assert clinic is not None
            assert clinic.appointment_price == Decimal("95.00")

        # a price change can succeed after the booking commits
        with session_factory() as db:
            db.execute(
                update(Clinic)
                .where(Clinic.id == clinic_id)
                .values(appointment_price=Decimal("110.00"))
            )
            db.commit()

        # a new booking using the old approved price must fail
        with session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                create_appointment(
                    db,
                    payload,
                    patient_id=patient_id,
                    now=datetime.now(UTC),
                    expected_price=Decimal("95.00"),
                )

            assert exc.value.status_code == 409
            assert "price changed" in str(exc.value.detail).lower()

    finally:
        release_booking.set()

        # remove committed records without touching other tests
        with session_factory() as db:
            db.execute(
                delete(Appointment).where(Appointment.optometrist_id == doctor_id)
            )
            db.execute(
                delete(WorkingSchedule).where(
                    WorkingSchedule.optometrist_id == doctor_id
                )
            )
            db.execute(
                delete(OptometristClinic).where(
                    OptometristClinic.optometrist_id == doctor_id
                )
            )
            db.execute(delete(Patient).where(Patient.id == patient_id))
            db.execute(delete(Optometrist).where(Optometrist.id == doctor_id))
            db.execute(
                delete(AppointmentService).where(AppointmentService.id == service_id)
            )
            db.execute(delete(Clinic).where(Clinic.id == clinic_id))
            db.commit()
