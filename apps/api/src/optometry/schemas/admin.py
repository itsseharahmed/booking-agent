"""Administrator authentication schemas."""

from pydantic import BaseModel, EmailStr

from optometry.schemas.auth import TokenRead


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


__all__ = ["AdminLogin", "TokenRead"]
