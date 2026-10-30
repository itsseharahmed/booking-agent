from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    clinic_id: int = Field(gt=0)
    optometrist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: datetime


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
