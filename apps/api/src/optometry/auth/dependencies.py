"""FastAPI dependency for authenticated patients."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from optometry.core.config import get_jwt_secret_key
from optometry.core.security import JWT_ALGORITHM
from optometry.db.models.patient import Patient
from optometry.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_patient(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> Patient:
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

        if payload.get("type") != "access":
            raise unauthorized

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdecimal():
            raise unauthorized

        patient_id = int(subject)
        if patient_id <= 0:
            raise unauthorized

    except jwt.InvalidTokenError as exc:
        raise unauthorized from exc

    patient = db.get(Patient, patient_id)

    if patient is None or not patient.is_active:
        raise unauthorized

    return patient
