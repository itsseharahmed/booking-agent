"""Read-only appointment availability API."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from optometry.availability.service import get_availability
from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES
from optometry.db.session import get_db
from optometry.schemas.availability import (
    AvailabilityRead,
    AvailabilitySlotRead,
)

router = APIRouter(prefix="/availability", tags=["Availability"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=AvailabilityRead)
def list_availability(
    db: DbSession,
    clinic_id: Annotated[int, Query(gt=0)],
    optometrist_id: Annotated[int, Query(gt=0)],
    service_id: Annotated[int, Query(gt=0)],
    appointment_date: date,
) -> AvailabilityRead:
    """List future appointment slots for a clinic and optometrist."""

    price, slots = get_availability(
        db=db,
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        appointment_date=appointment_date,
        now=get_current_time(),
    )

    return AvailabilityRead(
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        appointment_date=appointment_date,
        timezone="America/Toronto",
        duration_minutes=APPOINTMENT_DURATION_MINUTES,
        appointment_price=price,
        slots=[AvailabilitySlotRead(start=slot.start, end=slot.end) for slot in slots],
    )


def get_current_time() -> datetime:
    """Provide a replaceable UTC clock for availability queries."""
    return datetime.now(UTC)
