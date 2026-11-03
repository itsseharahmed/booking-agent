# Database-backed appointment availability lookup.

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


# loads the availability record for a specific clinic, doctor, and date.
def get_availability(
    *,
    db: Session,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    appointment_date: date,
    now: datetime,
) -> tuple[Decimal, list[AvailabilitySlot]]:
    # fetches the clinic so we can confirm it exists before checking availability.
    clinic = db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")

    # fetches the optometrist to verify the doctor is valid for this booking.
    optometrist = db.get(Optometrist, optometrist_id)
    if optometrist is None:
        raise HTTPException(status_code=404, detail="Optometrist not found")

    # fetches the appointment service to make sure the requested service is known.
    service = db.get(AppointmentService, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    # if the clinic is inactive, no appointments are available for it.
    if not clinic.is_active:
        return clinic.appointment_price, []

    # if the optometrist is inactive, they cannot take new bookings.
    if not optometrist.is_active:
        return clinic.appointment_price, []

    # if the service is inactive, it should not be offered to patients.
    if not service.is_active:
        return clinic.appointment_price, []

    # confirms the optometrist is actually assigned to the clinic.
    assignment = db.get(
        OptometristClinic,
        (optometrist_id, clinic_id),
    )

    # if no assignment exists, the doctor is not scheduled at this location.
    if assignment is None:
        return clinic.appointment_price, []

    # uses the weekday to find the matching working schedule for that date.
    weekday = appointment_date.weekday()

    # reads the active shift for the clinic and doctor on this weekday.
    schedule = db.scalar(
        select(WorkingSchedule).where(
            WorkingSchedule.clinic_id == clinic_id,
            WorkingSchedule.optometrist_id == optometrist_id,
            WorkingSchedule.day_of_week == weekday,
            WorkingSchedule.is_active.is_(True),
        )
    )

    # no schedule means there is no shift to book from on this day.
    if schedule is None:
        return clinic.appointment_price, []

    # creates all possible time slots within the active shift window.
    slots = generate_slots(
        appointment_date=appointment_date,
        shift_start=schedule.start_time,
        shift_end=schedule.end_time,
        now=now,
    )

    # if no future slots are possible, return the empty list immediately.
    if not slots:
        return clinic.appointment_price, slots

    # finds the earliest and latest times in the generated window for overlap checks.
    window_start = min(slot.start for slot in slots).astimezone(UTC)
    window_end = max(slot.end for slot in slots).astimezone(UTC)

    # loads all booked appointments that overlap this time window.
    booked_appointments = db.scalars(
        select(Appointment).where(
            Appointment.optometrist_id == optometrist_id,
            Appointment.status == "booked",
            Appointment.start_at < window_end,
            Appointment.end_at > window_start,
        )
    ).all()

    # converts booked appointments into time ranges that can be compared with available slots.
    occupied = [
        AvailabilitySlot(
            start=appointment.start_at,
            end=appointment.end_at,
        )
        for appointment in booked_appointments
    ]

    # removes any slot that overlaps with an already booked appointment.
    slots = exclude_occupied_slots(slots, occupied)

    # returns the clinic's standard price plus only the free appointment slots.
    return clinic.appointment_price, slots
