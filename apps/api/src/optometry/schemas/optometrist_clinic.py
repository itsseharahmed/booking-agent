"""Pydantic schemas for optometrist-clinic assignments."""

from pydantic import BaseModel, ConfigDict, Field


class OptometristClinicCreate(BaseModel):
    """Identify the clinic to assign."""

    clinic_id: int = Field(gt=0)


class OptometristClinicRead(BaseModel):
    """Return an optometrist-clinic assignment."""

    model_config = ConfigDict(from_attributes=True)

    optometrist_id: int
    clinic_id: int
