"""LangChain tool for confirmed appointment booking."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool
from redis import Redis
from sqlalchemy.orm import Session

from optometry.agent.tools.confirmation import BookingDetails, consume_confirmation
from optometry.booking.service import create_appointment
from optometry.cache.availability_cache import invalidate_availability
from optometry.cache.redis_client import create_redis_client
from optometry.db.session import SessionLocal
from optometry.schemas.appointment import AppointmentCreate

TORONTO = ZoneInfo("America/Toronto")


def fetch_book_appointment(
    *,
    db: Session,
    patient_id: int,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    start_at: datetime,
    now: datetime,
    redis_client: Redis | None = None,
) -> dict[str, Any]:
    payload = AppointmentCreate(
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        start_at=start_at,
    )

    try:
        appointment = create_appointment(db, payload, patient_id=patient_id, now=now)
    except HTTPException as exc:
        return {"error": str(exc.detail), "status_code": exc.status_code}

    if redis_client is not None:
        invalidate_availability(
            client=redis_client,
            optometrist_id=appointment.optometrist_id,
            appointment_date=appointment.start_at.astimezone(TORONTO).date(),
        )

    return {
        "appointment_id": appointment.id,
        "clinic_id": appointment.clinic_id,
        "optometrist_id": appointment.optometrist_id,
        "service_id": appointment.service_id,
        "start_at": appointment.start_at.isoformat(),
        "end_at": appointment.end_at.isoformat(),
        "appointment_price": str(appointment.appointment_price),
        "status": appointment.status,
    }


def create_booking_tool(*, patient_id: int, confirmation_token: str) -> BaseTool:
    if patient_id <= 0:
        raise ValueError("A valid authenticated patient is required")

    if not confirmation_token:
        raise ValueError("A confirmation token is required")

    def book_appointment() -> dict[str, Any]:
        """Execute the exact booking approved by the patient."""
        with create_redis_client() as redis_client:
            approved = consume_confirmation(
                client=redis_client,
                patient_id=patient_id,
                token=confirmation_token,
                action="book",
            )

            if not isinstance(approved, BookingDetails):
                raise PermissionError("Wrong confirmation action")

            with SessionLocal() as db:
                return fetch_book_appointment(
                    db=db,
                    patient_id=patient_id,
                    clinic_id=approved.clinic_id,
                    optometrist_id=approved.optometrist_id,
                    service_id=approved.service_id,
                    start_at=approved.start_at,
                    now=datetime.now(UTC),
                    redis_client=redis_client,
                )

    return StructuredTool.from_function(
        func=book_appointment,
        name="book_appointment",
        description="Execute a one-time, server-approved patient booking.",
    )
