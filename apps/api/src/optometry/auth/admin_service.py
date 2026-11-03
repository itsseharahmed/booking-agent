# Administrator authentication.

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from optometry.core.security import verify_password
from optometry.db.models.admin import Admin
from optometry.schemas.admin import AdminLogin


# validates the admin credentials.
def authenticate_admin(
    db: Session,
    payload: AdminLogin,
) -> Admin:
    email = str(payload.email).strip().lower()

    admin = db.scalar(select(Admin).where(func.lower(Admin.email) == email))

    if (
        admin is None
        or not admin.is_active
        or not verify_password(
            payload.password,
            admin.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return admin
