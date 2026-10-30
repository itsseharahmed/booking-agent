"""Database-backed appointment availability lookup."""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from optometry.availability.engine import (
    AvailabilitySlot,
    exclude_occupied_slots,
    generate_slots,
)
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule


def get_availability(
    *,
    db: Session,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    appointment_date: date,
    now: datetime,
) -> tuple[Decimal, list[AvailabilitySlot]]:
    """Return clinic price and available slots for a requested date."""

    clinic = db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")

    optometrist = db.get(Optometrist, optometrist_id)
    if optometrist is None:
        raise HTTPException(status_code=404, detail="Optometrist not found")

    service = db.get(AppointmentService, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    if not clinic.is_active:
        return clinic.appointment_price, []

    if not optometrist.is_active:
        return clinic.appointment_price, []

    if not service.is_active:
        return clinic.appointment_price, []

    assignment = db.get(
        OptometristClinic,
        (optometrist_id, clinic_id),
    )

    if assignment is None:
        return clinic.appointment_price, []

    weekday = appointment_date.weekday()

    schedule = db.scalar(
        select(WorkingSchedule).where(
            WorkingSchedule.clinic_id == clinic_id,
            WorkingSchedule.optometrist_id == optometrist_id,
            WorkingSchedule.day_of_week == weekday,
            WorkingSchedule.is_active.is_(True),
        )
    )

    if schedule is None:
        return clinic.appointment_price, []

    slots = generate_slots(
        appointment_date=appointment_date,
        shift_start=schedule.start_time,
        shift_end=schedule.end_time,
        now=now,
    )

    if not slots:
        return clinic.appointment_price, slots

    window_start = min(slot.start for slot in slots).astimezone(UTC)
    window_end = max(slot.end for slot in slots).astimezone(UTC)

    booked_appointments = db.scalars(
        select(Appointment).where(
            Appointment.optometrist_id == optometrist_id,
            Appointment.status == "booked",
            Appointment.start_at < window_end,
            Appointment.end_at > window_start,
        )
    ).all()

    occupied = [
        AvailabilitySlot(
            start=appointment.start_at,
            end=appointment.end_at,
        )
        for appointment in booked_appointments
    ]

    slots = exclude_occupied_slots(slots, occupied)

    return clinic.appointment_price, slots
