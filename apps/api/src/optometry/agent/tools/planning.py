"""Read-only tools for planning appointment actions."""

from datetime import datetime
from typing import Annotated, Any, Literal

from langchain_core.tools import tool
from pydantic import Field


# records a proposed booking without executing it
@tool
def propose_booking(
    clinic_id: Annotated[int, Field(gt=0)],
    optometrist_id: Annotated[int, Field(gt=0)],
    service_id: Annotated[int, Field(gt=0)],
    start_at: Annotated[
        datetime,
        Field(description="Selected appointment start with timezone offset"),
    ],
) -> dict[str, Any]:
    """Propose a booking using a verified available appointment slot."""
    if start_at.tzinfo is None or start_at.utcoffset() is None:
        raise ValueError("Appointment time must include a timezone offset")

    return {
        "action": "book",
        "clinic_id": clinic_id,
        "optometrist_id": optometrist_id,
        "service_id": service_id,
        "start_at": start_at.isoformat(),
        "requires_confirmation": True,
    }


# records a proposed cancellation without executing it
@tool
def propose_cancellation(
    appointment_id: Annotated[int, Field(gt=0)],
) -> dict[str, Any]:
    """Propose cancellation of an existing appointment for patient approval."""
    return {
        "action": "cancel",
        "appointment_id": appointment_id,
        "requires_confirmation": True,
    }


ActionType = Literal["book", "cancel"]
