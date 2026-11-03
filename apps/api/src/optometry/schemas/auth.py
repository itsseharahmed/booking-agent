"""Patient authentication request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# handles the PatientRegister workflow.
class PatientRegister(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("first_name", "last_name")
    @classmethod
    # handles the normalize name workflow.
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name cannot be blank")
        return value


# handles the PatientLogin workflow.
class PatientLogin(BaseModel):
    email: EmailStr
    password: str


# handles the PatientRead workflow.
class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime


# handles the TokenRead workflow.
class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
