"""LangChain tool for appointment booking."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from optometry.booking.service import create_appointment
from optometry.db.session import SessionLocal

# update this import if your AppointmentCreate schema is elsewhere
from optometry.schemas.appointment import AppointmentCreate


class BookingInput(BaseModel):
    clinic_id: Annotated[int, Field(gt=0)]
    optometrist_id: Annotated[int, Field(gt=0)]
    service_id: Annotated[int, Field(gt=0)]
    start_at: datetime


# books an appointment for an authenticated patient
def fetch_book_appointment(
    *,
    db: Session,
    patient_id: int,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    start_at: datetime,
    now: datetime,
) -> dict[str, Any]:
    payload = AppointmentCreate(
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        start_at=start_at,
    )

    try:
        appointment = create_appointment(
            db,
            payload,
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
        "clinic_id": appointment.clinic_id,
        "optometrist_id": appointment.optometrist_id,
        "service_id": appointment.service_id,
        "start_at": appointment.start_at.isoformat(),
        "end_at": appointment.end_at.isoformat(),
        "appointment_price": str(appointment.appointment_price),
        "status": appointment.status,
    }


# creates a booking tool scoped to a confirmed patient request
def create_booking_tool(
    *,
    patient_id: int,
    confirmed: bool,
) -> BaseTool:
    if patient_id <= 0:
        raise ValueError("A valid authenticated patient is required")

    if not confirmed:
        raise ValueError("Patient confirmation is required")

    def book_appointment(
        clinic_id: int,
        optometrist_id: int,
        service_id: int,
        start_at: datetime,
    ) -> dict[str, Any]:
        """Book an appointment after explicit patient confirmation."""
        with SessionLocal() as db:
            return fetch_book_appointment(
                db=db,
                patient_id=patient_id,
                clinic_id=clinic_id,
                optometrist_id=optometrist_id,
                service_id=service_id,
                start_at=start_at,
                now=datetime.now(UTC),
            )

    return StructuredTool.from_function(
        func=book_appointment,
        name="book_appointment",
        description=(
            "Create an optometry appointment for the authenticated patient. "
            "Only available after the patient confirms the booking."
        ),
        args_schema=BookingInput,
    )
