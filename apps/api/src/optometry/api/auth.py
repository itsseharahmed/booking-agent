# patient registration and login endpoints.

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from optometry.auth.service import authenticate_patient, register_patient
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import create_access_token
from optometry.db.models.patient import Patient
from optometry.db.session import get_db
from optometry.schemas.auth import (
    PatientLogin,
    PatientRead,
    PatientRegister,
    TokenRead,
)

# router for this api module.
router = APIRouter(prefix="/auth", tags=["authentication"])

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=PatientRead, status_code=201)
# handles the register workflow.
def register(
    payload: PatientRegister,
    db: DbSession,
) -> Patient:
    # calls the service that hashes the password and saves the patient.
    return register_patient(db, payload)


@router.post("/login", response_model=TokenRead)
# logs the user in and returns a token.
def login(
    payload: PatientLogin,
    db: DbSession,
) -> TokenRead:
    # validates the email and password before issuing a token.
    patient = authenticate_patient(db, payload)

    # creates the JWT with the patient id for later requests.
    token = create_access_token(
        patient_id=patient.id,
        secret_key=get_jwt_secret_key(),
    )

    return TokenRead(access_token=token)
