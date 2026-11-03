# Authenticated patient profile endpoints.

from typing import Annotated

from fastapi import APIRouter, Depends

from optometry.auth.dependencies import get_current_patient
from optometry.db.models.patient import Patient
from optometry.schemas.auth import PatientRead

# router for this api module.
router = APIRouter(prefix="/patients", tags=["patients"])

# stores the authenticated user for this endpoint.
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]


@router.get("/me", response_model=PatientRead)
# loads the my profile record.
def get_my_profile(
    patient: CurrentPatient,
) -> Patient:
    return patient
