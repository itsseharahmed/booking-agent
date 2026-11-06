"""Schemas for admin-managed clinic information."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClinicKnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insurance_info: str | None = Field(default=None, max_length=2000)
    parking_info: str | None = Field(default=None, max_length=2000)
    accessibility_info: str | None = Field(default=None, max_length=2000)
    appointment_policy: str | None = Field(default=None, max_length=2000)
    additional_info: str | None = Field(default=None, max_length=2000)


class ClinicKnowledgeRead(ClinicKnowledgeUpdate):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: int
    updated_at: datetime
