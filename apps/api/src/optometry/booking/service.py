"""Booking operations and appointment validation."""

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


def create_appointment(
    db: Session,
    payload: AppointmentCreate,
    *,
    now: datetime,
) -> Appointment:
    if payload.start_at.tzinfo is None or payload.start_at.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="start_at must include a timezone offset",
        )

    requested_start = payload.start_at.astimezone(UTC)

    if requested_start <= now.astimezone(UTC):
        raise HTTPException(
            status_code=422,
            detail="Cannot book a past or current appointment slot",
        )

    local_date = requested_start.astimezone(TORONTO).date()

    price, slots = get_availability(
        db=db,
        clinic_id=payload.clinic_id,
        optometrist_id=payload.optometrist_id,
        service_id=payload.service_id,
        appointment_date=local_date,
        now=now,
    )

    matching_slot = next(
        (slot for slot in slots if slot.start.astimezone(UTC) == requested_start),
        None,
    )

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

    appointment = Appointment(
        clinic_id=payload.clinic_id,
        optometrist_id=payload.optometrist_id,
        service_id=payload.service_id,
        start_at=requested_start,
        end_at=requested_start + timedelta(minutes=APPOINTMENT_DURATION_MINUTES),
        status="booked",
        appointment_price=price,
    )

    try:
        with db.begin_nested():
            db.add(appointment)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Appointment slot is already booked or conflicts with another booking",
        ) from exc

    db.commit()
    db.refresh(appointment)

    return appointment


def get_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    return appointment


def list_appointments(
    db: Session,
    *,
    clinic_id: int | None = None,
    optometrist_id: int | None = None,
    status: str | None = None,
) -> list[Appointment]:
    query = select(Appointment)

    if clinic_id is not None:
        query = query.where(Appointment.clinic_id == clinic_id)

    if optometrist_id is not None:
        query = query.where(Appointment.optometrist_id == optometrist_id)

    if status is not None:
        query = query.where(Appointment.status == status)

    query = query.order_by(Appointment.start_at, Appointment.id)

    return list(db.scalars(query).all())


def cancel_appointment(
    db: Session,
    appointment_id: int,
    *,
    now: datetime,
) -> Appointment:
    appointment = db.scalar(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    )

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Appointment is already cancelled",
        )

    if appointment.start_at <= now:
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel an appointment that has already started",
        )

    appointment.status = "cancelled"
    appointment.cancelled_at = now

    db.commit()
    db.refresh(appointment)

    return appointment
