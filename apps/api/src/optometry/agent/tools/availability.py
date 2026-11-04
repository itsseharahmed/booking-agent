"""LangChain tool for appointment availability."""

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import HTTPException
from langchain_core.tools import tool
from pydantic import Field
from sqlalchemy.orm import Session

from optometry.availability.service import get_availability
from optometry.db.session import SessionLocal


# retrieves appointment availability using existing booking rules
def fetch_appointment_availability(
    *,
    db: Session,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    appointment_date: date,
    now: datetime,
) -> dict[str, Any]:
    try:
        price, slots = get_availability(
            db=db,
            clinic_id=clinic_id,
            optometrist_id=optometrist_id,
            service_id=service_id,
            appointment_date=appointment_date,
            now=now,
        )
    except HTTPException as exc:
        return {
            "error": str(exc.detail),
            "status_code": exc.status_code,
        }

    return {
        "clinic_id": clinic_id,
        "optometrist_id": optometrist_id,
        "service_id": service_id,
        "appointment_date": appointment_date.isoformat(),
        "appointment_price": str(price),
        "slots": [
            {
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
            }
            for slot in slots
        ],
    }


# exposes appointment availability to the booking agent


@tool
def check_appointment_availability(
    clinic_id: Annotated[int, Field(gt=0, description="Clinic ID")],
    optometrist_id: Annotated[int, Field(gt=0, description="Optometrist ID")],
    service_id: Annotated[int, Field(gt=0, description="Appointment service ID")],
    appointment_date: Annotated[date, Field(description="Date in YYYY-MM-DD format")],
) -> dict[str, Any]:
    """Check available appointment slots for a clinic, doctor, service, and date."""
    with SessionLocal() as db:
        return fetch_appointment_availability(
            db=db,
            clinic_id=clinic_id,
            optometrist_id=optometrist_id,
            service_id=service_id,
            appointment_date=appointment_date,
            now=datetime.now(UTC),
        )
