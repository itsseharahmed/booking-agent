"""LangChain tool for appointment cancellation."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from optometry.booking.service import cancel_appointment
from optometry.db.session import SessionLocal


class CancellationInput(BaseModel):
    appointment_id: Annotated[int, Field(gt=0)]


# cancels an appointment using existing booking rules
def fetch_cancel_appointment(
    *,
    db: Session,
    patient_id: int,
    appointment_id: int,
    now: datetime,
) -> dict[str, Any]:
    try:
        appointment = cancel_appointment(
            db,
            appointment_id,
            patient_id=patient_id,
            now=now,
        )
    except HTTPException as exc:
        return {
            "error": str(exc.detail),
            "status_code": exc.status_code,
        }

    return {
        "appointment_id": appointment.id,
        "status": appointment.status,
        "cancelled_at": (
            appointment.cancelled_at.isoformat()
            if appointment.cancelled_at is not None
            else None
        ),
    }


# creates a cancellation tool for an authenticated patient
def create_cancellation_tool(
    *,
    patient_id: int,
    confirmed: bool,
) -> BaseTool:
    if patient_id <= 0:
        raise ValueError("A valid authenticated patient is required")

    if not confirmed:
        raise ValueError("Patient confirmation is required")

    def cancel_patient_appointment(
        appointment_id: int,
    ) -> dict[str, Any]:
        """Cancel an appointment after explicit patient confirmation."""
        with SessionLocal() as db:
            return fetch_cancel_appointment(
                db=db,
                patient_id=patient_id,
                appointment_id=appointment_id,
                now=datetime.now(UTC),
            )

    return StructuredTool.from_function(
        func=cancel_patient_appointment,
        name="cancel_appointment",
        description=(
            "Cancel an existing appointment belonging to the authenticated "
            "patient. Only available after explicit patient confirmation."
        ),
        args_schema=CancellationInput,
    )
