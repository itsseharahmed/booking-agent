"""Pydantic schemas for clinic API requests and responses."""

from datetime import datetime
from decimal import Decimal

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
    appointment_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Require the same timezone for all clinic locations."""
        if value != "America/Toronto":
            raise ValueError("Clinic timezone must be America/Toronto")

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
    appointment_price: Decimal


class ClinicAppointmentPriceUpdate(BaseModel):
    """Update a clinic's standard appointment price."""

    appointment_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
