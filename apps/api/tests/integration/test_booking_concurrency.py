"""Concurrent booking integration tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from optometry.booking.service import create_appointment
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.patient import Patient
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.schemas.appointment import AppointmentCreate


# checks that concurrent bookings cannot reserve the same slot
def test_concurrent_bookings_cannot_overlap(test_engine, monkeypatch):
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    # create committed records visible to both transactions
    with session_factory() as db:
        clinic = Clinic(
            name="Concurrency Test Clinic",
            address_line1="123 Main Street",
            city="Toronto",
            province="Ontario",
            postal_code="M5V 2T6",
            country="CA",
            timezone="America/Toronto",
            appointment_price=Decimal("95.00"),
        )
        optometrist = Optometrist(
            first_name="Concurrent",
            last_name="Booking",
        )
        service = AppointmentService(
            name="Concurrency Test Eye Exam",
        )

        db.add_all([clinic, optometrist, service])
        db.flush()

        clinic_id = clinic.id
        optometrist_id = optometrist.id
        service_id = service.id

        db.add(
            OptometristClinic(
                optometrist_id=optometrist_id,
                clinic_id=clinic_id,
            )
        )

        target = datetime.now(UTC).date() + timedelta(days=21)
        target += timedelta(days=(0 - target.weekday()) % 7)

        db.add(
            WorkingSchedule(
                clinic_id=clinic_id,
                optometrist_id=optometrist_id,
                day_of_week=0,
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("10:00", "%H:%M").time(),
                is_active=True,
            )
        )

        db.commit()

    # select a valid slot using the real availability service
    import optometry.booking.service as booking_service
    from optometry.availability.service import get_availability

    with session_factory() as db:
        _, slots = get_availability(
            db=db,
            clinic_id=clinic_id,
            optometrist_id=optometrist_id,
            service_id=service_id,
            appointment_date=target,
            now=datetime.now(UTC),
        )

        assert slots
        start_at = slots[0].start

    payload = AppointmentCreate(
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        start_at=start_at,
    )

    barrier = Barrier(2, timeout=10)
    original = booking_service.get_availability

    # synchronize both bookings after availability validation
    def synchronized_availability(**kwargs):
        result = original(**kwargs)
        barrier.wait()
        return result

    monkeypatch.setattr(
        booking_service,
        "get_availability",
        synchronized_availability,
    )

    # use separate database connections for each booking
    def book(patient_id):
        with session_factory() as db:
            try:
                create_appointment(
                    db,
                    payload,
                    patient_id=patient_id,
                    now=datetime.now(UTC),
                )
                return 201
            except HTTPException as exc:
                db.rollback()
                return exc.status_code

    try:
        with session_factory() as db:
            patient1 = Patient(
                first_name="Concurrent",
                last_name="PatientOne",
                email="concurrency-one@example.com",
                password_hash="test-password-hash",
            )
            patient2 = Patient(
                first_name="Concurrent",
                last_name="PatientTwo",
                email="concurrency-two@example.com",
                password_hash="test-password-hash",
            )

            db.add_all([patient1, patient2])
            db.commit()

            patient_ids = (patient1.id, patient2.id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(book, patient_id) for patient_id in patient_ids]
            results = [future.result(timeout=20) for future in futures]

        assert sorted(results) == [201, 409]

        with session_factory() as db:
            count = db.scalar(
                select(func.count(Appointment.id)).where(
                    Appointment.optometrist_id == optometrist_id,
                    Appointment.status == "booked",
                )
            )
            assert count == 1

    finally:
        # remove committed records in foreign-key order
        with session_factory() as db:
            db.execute(
                delete(Appointment).where(Appointment.optometrist_id == optometrist_id)
            )
            db.execute(
                delete(WorkingSchedule).where(
                    WorkingSchedule.optometrist_id == optometrist_id
                )
            )
            db.execute(
                delete(OptometristClinic).where(
                    OptometristClinic.optometrist_id == optometrist_id
                )
            )
            db.execute(
                delete(Patient).where(
                    Patient.email.in_(
                        [
                            "concurrency-one@example.com",
                            "concurrency-two@example.com",
                        ]
                    )
                )
            )
            db.execute(delete(Optometrist).where(Optometrist.id == optometrist_id))
            db.execute(
                delete(AppointmentService).where(AppointmentService.id == service_id)
            )
            db.execute(delete(Clinic).where(Clinic.id == clinic_id))
            db.commit()
