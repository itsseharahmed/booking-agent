from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_serializer


# handles the AppointmentCreate workflow.
class AppointmentCreate(BaseModel):
    clinic_id: int = Field(gt=0)
    optometrist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: datetime


# handles the AppointmentRead workflow.
class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("start_at", "end_at")
    # handles the serialize toronto time workflow.
    def serialize_toronto_time(self, value: datetime) -> str:
        return value.astimezone(ZoneInfo("America/Toronto")).isoformat()

    id: int
    clinic_id: int
    optometrist_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    status: Literal["booked", "cancelled"]
    appointment_price: Decimal
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
