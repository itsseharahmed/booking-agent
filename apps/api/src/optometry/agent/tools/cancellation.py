"""LangChain tool for confirmed appointment cancellation."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool
from redis import Redis
from sqlalchemy.orm import Session

from optometry.agent.tools.confirmation import CancellationDetails, consume_confirmation
from optometry.booking.service import cancel_appointment
from optometry.cache.availability_cache import invalidate_availability
from optometry.cache.redis_client import create_redis_client
from optometry.db.session import SessionLocal

TORONTO = ZoneInfo("America/Toronto")


def fetch_cancel_appointment(
    *,
    db: Session,
    patient_id: int,
    appointment_id: int,
    now: datetime,
    redis_client: Redis | None = None,
) -> dict[str, Any]:
    try:
        appointment = cancel_appointment(
            db,
            appointment_id,
            patient_id=patient_id,
            now=now,
        )
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
        "status": appointment.status,
        "cancelled_at": (
            appointment.cancelled_at.isoformat()
            if appointment.cancelled_at is not None
            else None
        ),
    }


def create_cancellation_tool(*, patient_id: int, confirmation_token: str) -> BaseTool:
    if patient_id <= 0:
        raise ValueError("A valid authenticated patient is required")

    if not confirmation_token:
        raise ValueError("A confirmation token is required")

    def cancel_patient_appointment() -> dict[str, Any]:
        """Cancel the exact appointment approved by the patient."""
        with create_redis_client() as redis_client:
            approved = consume_confirmation(
                client=redis_client,
                patient_id=patient_id,
                token=confirmation_token,
                action="cancel",
            )

            if not isinstance(approved, CancellationDetails):
                raise PermissionError("Wrong confirmation action")

            with SessionLocal() as db:
                return fetch_cancel_appointment(
                    db=db,
                    patient_id=patient_id,
                    appointment_id=approved.appointment_id,
                    now=datetime.now(UTC),
                    redis_client=redis_client,
                )

    return StructuredTool.from_function(
        func=cancel_patient_appointment,
        name="cancel_appointment",
        description="Execute a one-time, server-approved cancellation.",
    )
