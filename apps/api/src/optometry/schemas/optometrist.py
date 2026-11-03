"""Pydantic schemas for optometrist API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# handles the OptometristCreate workflow.
class OptometristCreate(BaseModel):
    """Validate data required to create an optometrist."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    license_number: str | None = Field(default=None, max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    # validates the required name input.
    def validate_required_name(cls, value: str) -> str:
        """Trim whitespace and reject empty names."""
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Name cannot be empty or whitespace")

        return cleaned


# handles the OptometristRead workflow.
class OptometristRead(BaseModel):
    """Define the optometrist data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    license_number: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# handles the OptometristUpdate workflow.
class OptometristUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    license_number: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    # validates the update input.
    def validate_update(self) -> "OptometristUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in {
                "license_number",
            }:
                raise ValueError(f"{field} cannot be null")

        return self
