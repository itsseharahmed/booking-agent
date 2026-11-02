"""Create administrator accounts securely."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.core.security import hash_password
from optometry.db.models.admin import Admin


def create_admin(
    *,
    db: Session,
    email: str,
    password: str,
) -> Admin:
    normalized_email = email.strip().lower()

    if (
        not normalized_email
        or normalized_email.count("@") != 1
        or "." not in normalized_email.split("@")[-1]
    ):
        raise ValueError("Invalid email address")

    if not 12 <= len(password) <= 128:
        raise ValueError("Password must be at least 12 and at most 128 characters")

    existing = db.scalar(
        select(Admin.id).where(func.lower(Admin.email) == normalized_email)
    )

    if existing is not None:
        raise ValueError("Administrator with this email already exists")

    admin = Admin(
        email=normalized_email,
        password_hash=hash_password(password),
        is_active=True,
    )

    try:
        with db.begin_nested():
            db.add(admin)
            db.flush()
    except IntegrityError as exc:
        raise ValueError("Administrator with this email already exists") from exc

    db.commit()
    db.refresh(admin)

    return admin
