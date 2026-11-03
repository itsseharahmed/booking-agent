# Booking operations and appointment validation.

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.availability.service import get_availability
from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES
from optometry.db.models.appointment import Appointment
from optometry.schemas.appointment import AppointmentCreate

TORONTO = ZoneInfo("America/Toronto")


# creates a new appointment and saves it in the database.
def create_appointment(
    db: Session,
    payload: AppointmentCreate,
    *,
    patient_id: int,
    now: datetime,
) -> Appointment:
    # timezone-aware input is required so comparisons and scheduling stay consistent.
    if payload.start_at.tzinfo is None or payload.start_at.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="start_at must include a timezone offset",
        )

    # convert the requested start into UTC so the system compares all times in one zone.
    requested_start = payload.start_at.astimezone(UTC)

    # a patient cannot book a slot that is already in the past or current.
    if requested_start <= now.astimezone(UTC):
        raise HTTPException(
            status_code=422,
            detail="Cannot book a past or current appointment slot",
        )

    # determine the Toronto date used to find valid availability for that day.
    local_date = requested_start.astimezone(TORONTO).date()

    # ask the availability layer for the current price and candidate free slots.
    price, slots = get_availability(
        db=db,
        clinic_id=payload.clinic_id,
        optometrist_id=payload.optometrist_id,
        service_id=payload.service_id,
        appointment_date=local_date,
        now=now,
    )

    # find the exact slot that matches the requested appointment start time.
    matching_slot = next(
        (slot for slot in slots if slot.start.astimezone(UTC) == requested_start),
        None,
    )

    # if the selected start is not available, reject it and check whether another booking conflict exists.
    if matching_slot is None:
        requested_end = requested_start + timedelta(
            minutes=APPOINTMENT_DURATION_MINUTES
        )

        existing_booking = db.scalar(
            select(Appointment.id).where(
                Appointment.optometrist_id == payload.optometrist_id,
                Appointment.status == "booked",
                Appointment.start_at < requested_end,
                Appointment.end_at > requested_start,
            )
        )

        if existing_booking is not None:
            raise HTTPException(
                status_code=409,
                detail="Appointment slot is already booked",
            )

        raise HTTPException(
            status_code=422,
            detail="Requested start time is not an available appointment slot",
        )

    # build the appointment using the validated slot and the clinic's price.
    appointment = Appointment(
        clinic_id=payload.clinic_id,
        optometrist_id=payload.optometrist_id,
        service_id=payload.service_id,
        start_at=requested_start,
        end_at=requested_start + timedelta(minutes=APPOINTMENT_DURATION_MINUTES),
        status="booked",
        appointment_price=price,
        patient_id=patient_id,
    )

    # save the new appointment inside a nested transaction to prevent partial writes on conflict.
    try:
        with db.begin_nested():
            db.add(appointment)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Appointment slot is already booked or conflicts with another booking",
        ) from exc

    # commit the transaction and reload the final saved record.
    db.commit()
    db.refresh(appointment)

    return appointment


# loads one appointment for the current patient only.
def get_appointment(
    db: Session,
    appointment_id: int,
    *,
    patient_id: int,
) -> Appointment:
    # look up the specific appointment under the patient's ownership.
    appointment = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id,
        )
    )

    # if there is no match, the patient is asking for a record they do not own.
    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    return appointment


# lists the patient's appointments with optional filters.
def list_appointments(
    db: Session,
    *,
    patient_id: int,
    clinic_id: int | None = None,
    optometrist_id: int | None = None,
    status: str | None = None,
) -> list[Appointment]:
    # start from the patient's appointments and add filters as needed.
    query = select(Appointment).where(Appointment.patient_id == patient_id)

    # filter by clinic if the request includes one.
    if clinic_id is not None:
        query = query.where(Appointment.clinic_id == clinic_id)

    # filter by optometrist if the request includes one.
    if optometrist_id is not None:
        query = query.where(Appointment.optometrist_id == optometrist_id)

    # filter by booking state when a status is supplied.
    if status is not None:
        query = query.where(Appointment.status == status)

    # return the appointments in a predictable order by time and id.
    query = query.order_by(
        Appointment.start_at,
        Appointment.id,
    )

    return list(db.scalars(query).all())


# marks an appointment as cancelled if it is still active and not started.
def cancel_appointment(
    db: Session,
    appointment_id: int,
    *,
    patient_id: int,
    now: datetime,
) -> Appointment:
    # lock the row while checking status so two cancellations cannot race each other.
    appointment = db.scalar(
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id,
        )
        .with_for_update()
    )

    # no matching appointment means this patient cannot cancel it.
    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    # already cancelled items should not be cancelled again.
    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Appointment is already cancelled",
        )

    # appointments cannot be cancelled once they have already started.
    if appointment.start_at <= now:
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel an appointment that has already started",
        )

    # update the state to cancelled and record when the cancellation happened.
    appointment.status = "cancelled"
    appointment.cancelled_at = now

    db.commit()
    db.refresh(appointment)

    return appointment
