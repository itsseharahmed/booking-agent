"""Authenticated agent confirmation endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy.orm import Session

from optometry.agent.proposals import (
    ActionProposal,
    BookingProposal,
    CancellationProposal,
)
from optometry.agent.tools.booking import fetch_book_appointment
from optometry.agent.tools.cancellation import fetch_cancel_appointment
from optometry.agent.tools.confirmation import (
    BookingDetails,
    CancellationDetails,
    confirm_request,
    consume_confirmation,
    prepare_confirmation,
)
from optometry.auth.dependencies import get_current_patient
from optometry.availability.service import get_availability
from optometry.booking.service import get_appointment
from optometry.cache.redis_client import create_redis_client
from optometry.db.models.patient import Patient
from optometry.db.session import get_db

router = APIRouter(
    prefix="/agent/confirmations",
    tags=["agent-confirmations"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]

TORONTO = ZoneInfo("America/Toronto")


# provides redis for confirmation storage
def get_confirmation_redis() -> Redis:
    return create_redis_client()


RedisClient = Annotated[Redis, Depends(get_confirmation_redis)]


class BookingConfirmationRequest(BaseModel):
    clinic_id: int = Field(gt=0)
    optometrist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: datetime


class CancellationConfirmationRequest(BaseModel):
    appointment_id: int = Field(gt=0)


class ConfirmationPrepared(BaseModel):
    confirmation_token: str
    action: Literal["book", "cancel"]
    expires_in_seconds: int = 300
    details: dict[str, str | int]


class ConfirmationApproved(BaseModel):
    approved: bool


# prepares an exact booking for patient approval
@router.post("/book", response_model=ConfirmationPrepared)
def prepare_booking(
    payload: BookingConfirmationRequest,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> ConfirmationPrepared:
    if payload.start_at.tzinfo is None or payload.start_at.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="start_at must include a timezone offset",
        )

    now = datetime.now(UTC)
    requested_start = payload.start_at.astimezone(UTC)

    if requested_start <= now:
        raise HTTPException(
            status_code=422,
            detail="Appointment must be in the future",
        )

    appointment_date = requested_start.astimezone(TORONTO).date()

    price, slots = get_availability(
        db=db,
        clinic_id=payload.clinic_id,
        optometrist_id=payload.optometrist_id,
        service_id=payload.service_id,
        appointment_date=appointment_date,
        now=now,
    )

    matching_slot = next(
        (slot for slot in slots if slot.start.astimezone(UTC) == requested_start),
        None,
    )

    if matching_slot is None:
        raise HTTPException(
            status_code=409,
            detail="Requested appointment slot is unavailable",
        )

    token = prepare_confirmation(
        client=redis_client,
        patient_id=patient.id,
        action="book",
        details=BookingDetails(
            clinic_id=payload.clinic_id,
            optometrist_id=payload.optometrist_id,
            service_id=payload.service_id,
            start_at=requested_start,
            appointment_price=price,
        ),
    )

    return ConfirmationPrepared(
        confirmation_token=token,
        action="book",
        details={
            "clinic_id": payload.clinic_id,
            "optometrist_id": payload.optometrist_id,
            "service_id": payload.service_id,
            "start_at": requested_start.isoformat(),
            "appointment_price": str(Decimal(price)),
        },
    )


# prepares a patient-owned appointment for cancellation
@router.post("/cancel", response_model=ConfirmationPrepared)
def prepare_cancellation(
    payload: CancellationConfirmationRequest,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> ConfirmationPrepared:
    appointment = get_appointment(
        db,
        payload.appointment_id,
        patient_id=patient.id,
    )

    if appointment.status != "booked":
        raise HTTPException(
            status_code=409,
            detail="Appointment is not active",
        )

    if appointment.start_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Appointment has already started",
        )

    token = prepare_confirmation(
        client=redis_client,
        patient_id=patient.id,
        action="cancel",
        details=CancellationDetails(
            appointment_id=appointment.id,
        ),
    )

    return ConfirmationPrepared(
        confirmation_token=token,
        action="cancel",
        details={
            "appointment_id": appointment.id,
            "start_at": appointment.start_at.isoformat(),
        },
    )


# approves the prepared action for later execution
@router.post("/{token}/approve", response_model=ConfirmationApproved)
def approve_confirmation(
    token: str,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> ConfirmationApproved:
    approved = confirm_request(
        client=redis_client,
        patient_id=patient.id,
        token=token,
    )

    if not approved:
        raise HTTPException(
            status_code=409,
            detail="Confirmation is invalid, expired, or already approved",
        )

    return ConfirmationApproved(approved=True)


# executes the exact booking approved by the patient
@router.post("/{token}/execute/book")
def execute_confirmed_booking(
    token: str,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> dict[str, Any]:
    try:
        approved = consume_confirmation(
            client=redis_client,
            patient_id=patient.id,
            token=token,
            action="book",
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Booking confirmation is invalid, expired, or already used",
        ) from exc

    if not isinstance(approved, BookingDetails):
        raise HTTPException(
            status_code=409,
            detail="Invalid booking confirmation",
        )

    result = fetch_book_appointment(
        db=db,
        patient_id=patient.id,
        clinic_id=approved.clinic_id,
        optometrist_id=approved.optometrist_id,
        service_id=approved.service_id,
        start_at=approved.start_at,
        now=datetime.now(UTC),
        redis_client=redis_client,
        expected_price=approved.appointment_price,
    )

    if "error" in result:
        raise HTTPException(
            status_code=int(result["status_code"]),
            detail=str(result["error"]),
        )

    return result


# executes the exact cancellation approved by the patient
@router.post("/{token}/execute/cancel")
def execute_confirmed_cancellation(
    token: str,
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> dict[str, Any]:
    try:
        approved = consume_confirmation(
            client=redis_client,
            patient_id=patient.id,
            token=token,
            action="cancel",
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Cancellation confirmation is invalid, expired, or already used",
        ) from exc

    if not isinstance(approved, CancellationDetails):
        raise HTTPException(
            status_code=409,
            detail="Invalid cancellation confirmation",
        )

    result = fetch_cancel_appointment(
        db=db,
        patient_id=patient.id,
        appointment_id=approved.appointment_id,
        now=datetime.now(UTC),
        redis_client=redis_client,
    )

    if "error" in result:
        raise HTTPException(
            status_code=int(result["status_code"]),
            detail=str(result["error"]),
        )

    return result


# validates an agent proposal and prepares patient confirmation
@router.post("/prepare", response_model=ConfirmationPrepared)
def prepare_agent_proposal(
    payload: Annotated[ActionProposal, Body(discriminator="action")],
    db: DbSession,
    patient: CurrentPatient,
    redis_client: RedisClient,
) -> ConfirmationPrepared:
    if isinstance(payload, BookingProposal):
        return prepare_booking(
            payload=BookingConfirmationRequest(
                clinic_id=payload.clinic_id,
                optometrist_id=payload.optometrist_id,
                service_id=payload.service_id,
                start_at=payload.start_at,
            ),
            db=db,
            patient=patient,
            redis_client=redis_client,
        )

    if isinstance(payload, CancellationProposal):
        return prepare_cancellation(
            payload=CancellationConfirmationRequest(
                appointment_id=payload.appointment_id,
            ),
            db=db,
            patient=patient,
            redis_client=redis_client,
        )

    raise HTTPException(
        status_code=422,
        detail="Unsupported agent proposal",
    )
