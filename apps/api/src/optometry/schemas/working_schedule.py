"""Pydantic schemas for weekly working schedules."""

from datetime import time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkingScheduleCreate(BaseModel):
    """Validate a new weekly working shift."""

    optometrist_id: int = Field(gt=0)
    clinic_id: int = Field(gt=0)
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "WorkingScheduleCreate":
        """Require the shift to end after it starts."""
        if self.start_time >= self.end_time:
            raise ValueError("End time must be after start time")

        return self


class WorkingScheduleRead(BaseModel):
    """Return a weekly working shift."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    optometrist_id: int
    clinic_id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool


class WorkingScheduleUpdate(BaseModel):
    """Fields that may be changed on an existing shift."""

    clinic_id: int | None = Field(default=None, gt=0)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        """Do not allow null to replace required database values."""
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
