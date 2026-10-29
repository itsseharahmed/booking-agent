"""Appointment service API schemas."""

from datetime import datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def normalize_service_name(value: str) -> str:
    cleaned = " ".join(value.split())

    if not cleaned:
        raise ValueError("Service name cannot be empty")

    if len(cleaned) > 150:
        raise ValueError("Service name cannot exceed 150 characters")

    return cleaned


class AppointmentServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_service_name(value)


class AppointmentServiceUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_service_name(value)

    @model_validator(mode="after")
    def reject_invalid_nulls(self) -> Self:
        for field_name in self.model_fields_set:
            if field_name != "description" and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


class AppointmentServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
