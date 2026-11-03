# FastAPI dependency for authenticated administrators.

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from optometry.core.config import get_jwt_secret_key
from optometry.core.security import JWT_ALGORITHM
from optometry.db.models.admin import Admin
from optometry.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]


# loads the current admin record.
def get_current_admin(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> Admin:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret_key(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.InvalidTokenError as exc:
        raise unauthorized from exc

    if payload.get("type") != "access":
        raise unauthorized

    # a valid patient token must never authorize an admin operation.
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges required",
        )

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdecimal():
        raise unauthorized

    admin_id = int(subject)
    if admin_id <= 0:
        raise unauthorized

    admin = db.get(Admin, admin_id)

    if admin is None or not admin.is_active:
        raise unauthorized

    return admin
