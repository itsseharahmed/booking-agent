"""Authenticated clinic knowledge management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from optometry.auth.admin_dependencies import get_current_admin
from optometry.db.models.clinic import Clinic
from optometry.db.models.clinic_knowledge import ClinicKnowledge
from optometry.db.session import get_db
from optometry.schemas.clinic_knowledge import (
    ClinicKnowledgeRead,
    ClinicKnowledgeUpdate,
)

router = APIRouter(
    prefix="/admin/clinics",
    tags=["Admin Clinic Knowledge"],
    dependencies=[Depends(get_current_admin)],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/{clinic_id}/knowledge",
    response_model=ClinicKnowledgeRead,
)
def get_admin_clinic_knowledge(
    clinic_id: int,
    db: DbSession,
) -> ClinicKnowledge:
    # reject clinics that do not exist
    if db.get(Clinic, clinic_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found",
        )

    knowledge = db.get(ClinicKnowledge, clinic_id)

    if knowledge is None:
        raise HTTPException(
            status_code=404,
            detail="Clinic knowledge not found",
        )

    return knowledge


@router.put(
    "/{clinic_id}/knowledge",
    response_model=ClinicKnowledgeRead,
)
def update_admin_clinic_knowledge(
    clinic_id: int,
    payload: ClinicKnowledgeUpdate,
    db: DbSession,
) -> ClinicKnowledge:
    # check the parent clinic before updating
    if db.get(Clinic, clinic_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found",
        )

    knowledge = db.get(ClinicKnowledge, clinic_id)

    if knowledge is None:
        knowledge = ClinicKnowledge(clinic_id=clinic_id)
        db.add(knowledge)

    # replace stored information with the validated payload
    for field, value in payload.model_dump().items():
        setattr(knowledge, field, value)

    db.commit()
    db.refresh(knowledge)

    return knowledge
