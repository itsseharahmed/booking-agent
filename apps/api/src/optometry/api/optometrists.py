"""API endpoints for managing optometrists."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.session import get_db
from optometry.schemas.optometrist import OptometristCreate, OptometristRead
from optometry.schemas.optometrist_clinic import (
    OptometristClinicCreate,
    OptometristClinicRead,
)

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/optometrists", tags=["Optometrists"])


@router.post(
    "",
    response_model=OptometristRead,
    status_code=status.HTTP_201_CREATED,
)
def create_optometrist(
    payload: OptometristCreate,
    db: DbSession,
) -> Optometrist:
    """Create an optometrist."""

    optometrist = Optometrist(**payload.model_dump())

    db.add(optometrist)
    db.commit()
    db.refresh(optometrist)

    return optometrist


@router.get("", response_model=list[OptometristRead])
def list_optometrists(
    db: DbSession,
) -> list[Optometrist]:
    """Retrieve optometrists ordered by ID."""

    statement = select(Optometrist).order_by(Optometrist.id)

    return list(db.scalars(statement).all())


@router.post(
    "/{optometrist_id}/clinics",
    response_model=OptometristClinicRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_optometrist_to_clinic(
    optometrist_id: int,
    payload: OptometristClinicCreate,
    db: DbSession,
) -> OptometristClinic:
    """Assign an existing optometrist to an existing clinic."""

    optometrist = db.get(Optometrist, optometrist_id)

    if optometrist is None:
        raise HTTPException(
            status_code=404,
            detail="Optometrist not found",
        )

    clinic = db.get(Clinic, payload.clinic_id)

    if clinic is None:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found",
        )

    existing_assignment = db.get(
        OptometristClinic,
        (optometrist_id, payload.clinic_id),
    )

    if existing_assignment is not None:
        raise HTTPException(
            status_code=409,
            detail="Optometrist is already assigned to this clinic",
        )

    assignment = OptometristClinic(
        optometrist_id=optometrist_id,
        clinic_id=payload.clinic_id,
    )

    db.add(assignment)
    db.commit()

    return assignment
