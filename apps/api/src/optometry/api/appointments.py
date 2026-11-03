# authenticated patient appointment endpoints.

from datetime import UTC, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from redis import Redis
from sqlalchemy.orm import Session

from optometry.auth.dependencies import get_current_patient
from optometry.booking.service import (
    cancel_appointment,
    create_appointment,
    get_appointment,
    list_appointments,
)
from optometry.cache.availability_cache import invalidate_availability
from optometry.cache.redis_client import create_redis_client
from optometry.db.models.appointment import Appointment
from optometry.db.models.patient import Patient
from optometry.db.session import get_db
from optometry.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
)

# router for this api module.
router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
)

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]

# stores the authenticated user for this endpoint.
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]


# provides redis for appointment cache invalidation
def get_redis_client() -> Redis:
    return create_redis_client()


RedisClient = Annotated[Redis, Depends(get_redis_client)]
TORONTO = ZoneInfo("America/Toronto")


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=201,
)
def create_booking(
    payload: AppointmentCreate,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> Appointment:
    # create and commit the appointment before invalidating availability
    appointment = create_appointment(
        db,
        payload,
        patient_id=patient.id,
        now=datetime.now(UTC),
    )

    # invalidate every service for this doctor and local appointment date
    invalidate_availability(
        client=redis_client,
        optometrist_id=appointment.optometrist_id,
        appointment_date=appointment.start_at.astimezone(TORONTO).date(),
    )

    return appointment


@router.get("", response_model=list[AppointmentRead])
# loads the bookings record.
def get_bookings(
    db: DbSession,
    patient: CurrentPatient,
    clinic_id: Annotated[int | None, Query(gt=0)] = None,
    optometrist_id: Annotated[int | None, Query(gt=0)] = None,
    status: Literal["booked", "cancelled"] | None = None,
) -> list[Appointment]:
    # return the patient's appointment history, optionally filtered by clinic, doctor, or status.
    return list_appointments(
        db,
        patient_id=patient.id,
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        status=status,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentRead,
)
# loads the booking record.
def get_booking(
    appointment_id: int,
    db: DbSession,
    patient: CurrentPatient,
) -> Appointment:
    # fetch one appointment for the current patient, ensuring ownership is enforced.
    return get_appointment(
        db,
        appointment_id,
        patient_id=patient.id,
    )


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
)
def cancel_booking(
    appointment_id: int,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> Appointment:
    # commit the cancellation before invalidating availability
    appointment = cancel_appointment(
        db,
        appointment_id,
        patient_id=patient.id,
        now=datetime.now(UTC),
    )

    # invalidate the affected doctor and appointment date
    invalidate_availability(
        client=redis_client,
        optometrist_id=appointment.optometrist_id,
        appointment_date=appointment.start_at.astimezone(TORONTO).date(),
    )

    return appointment
