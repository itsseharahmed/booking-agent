"""Authenticated patient appointment endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from optometry.auth.dependencies import get_current_patient
from optometry.booking.service import (
    cancel_appointment,
    create_appointment,
    get_appointment,
    list_appointments,
)
from optometry.db.models.appointment import Appointment
from optometry.db.models.patient import Patient
from optometry.db.session import get_db
from optometry.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
)

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=201,
)
def create_booking(
    payload: AppointmentCreate,
    db: DbSession,
    patient: CurrentPatient,
) -> Appointment:
    return create_appointment(
        db,
        payload,
        patient_id=patient.id,
        now=datetime.now(UTC),
    )


@router.get("", response_model=list[AppointmentRead])
def get_bookings(
    db: DbSession,
    patient: CurrentPatient,
    clinic_id: Annotated[int | None, Query(gt=0)] = None,
    optometrist_id: Annotated[int | None, Query(gt=0)] = None,
    status: Literal["booked", "cancelled"] | None = None,
) -> list[Appointment]:
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
def get_booking(
    appointment_id: int,
    db: DbSession,
    patient: CurrentPatient,
) -> Appointment:
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
) -> Appointment:
    return cancel_appointment(
        db,
        appointment_id,
        patient_id=patient.id,
        now=datetime.now(UTC),
    )
