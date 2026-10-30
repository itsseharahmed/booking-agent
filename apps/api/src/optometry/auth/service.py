"""Patient registration and authentication."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.core.security import hash_password, verify_password
from optometry.db.models.patient import Patient
from optometry.schemas.auth import PatientLogin, PatientRegister


def register_patient(
    db: Session,
    payload: PatientRegister,
) -> Patient:
    email = str(payload.email).strip().lower()

    existing = db.scalar(select(Patient.id).where(func.lower(Patient.email) == email))

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    patient = Patient(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=email,
        password_hash=hash_password(payload.password),
    )

    try:
        with db.begin_nested():
            db.add(patient)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        ) from exc

    db.commit()
    db.refresh(patient)

    return patient


def authenticate_patient(
    db: Session,
    payload: PatientLogin,
) -> Patient:
    email = str(payload.email).strip().lower()

    patient = db.scalar(select(Patient).where(func.lower(Patient.email) == email))

    if (
        patient is None
        or not patient.is_active
        or not verify_password(
            payload.password,
            patient.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return patient
