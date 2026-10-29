"""Schemas for appointment availability responses."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class AvailabilitySlotRead(BaseModel):
    start: datetime
    end: datetime


class AvailabilityRead(BaseModel):
    clinic_id: int
    optometrist_id: int
    service_id: int
    appointment_date: date
    timezone: str
    duration_minutes: int
    appointment_price: Decimal
    slots: list[AvailabilitySlotRead]
