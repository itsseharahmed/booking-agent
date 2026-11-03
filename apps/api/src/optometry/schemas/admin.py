"""Administrator authentication schemas."""

from pydantic import BaseModel, EmailStr

from optometry.schemas.auth import TokenRead


# handles the AdminLogin workflow.
class AdminLogin(BaseModel):
    email: EmailStr
    password: str


__all__ = ["AdminLogin", "TokenRead"]
