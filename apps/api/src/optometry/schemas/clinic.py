"""Pydantic schemas for clinic API requests and responses."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClinicCreate(BaseModel):
    """Validate data required to create a clinic."""

    name: str = Field(min_length=1, max_length=150)
    address_line1: str = Field(min_length=1, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="CA", min_length=2, max_length=2)
    phone: str | None = Field(default=None, max_length=30)
    timezone: str = Field(default="America/Toronto")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Ensure the timezone is recognized by the IANA database."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Invalid IANA timezone") from exc

        return value

    @field_validator(
        "name",
        "address_line1",
        "city",
        "province",
        "postal_code",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Remove surrounding whitespace and reject empty text."""
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace")

        return cleaned


class ClinicRead(BaseModel):
    """Define the clinic data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address_line1: str
    address_line2: str | None
    city: str
    province: str
    postal_code: str
    country: str
    phone: str | None
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
