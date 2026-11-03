# API endpoints for managing optometrists.

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.auth.admin_dependencies import get_current_admin
from optometry.cache.admin_invalidation import invalidate_admin_availability
from optometry.cache.redis_client import create_redis_client
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.session import get_db
from optometry.schemas.optometrist import (
    OptometristCreate,
    OptometristRead,
    OptometristUpdate,
)
from optometry.schemas.optometrist_clinic import (
    OptometristClinicCreate,
    OptometristClinicRead,
)

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]

# router for this api module.
router = APIRouter(prefix="/optometrists", tags=["Optometrists"])

# provides redis for administrative cache invalidation
RedisClient = Annotated[Redis, Depends(create_redis_client)]


@router.post(
    "",
    response_model=OptometristRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
# creates a new optometrist.
def create_optometrist(
    payload: OptometristCreate, db: DbSession, redis_client: RedisClient
) -> Optometrist:
    """Create an optometrist."""

    optometrist = Optometrist(**payload.model_dump())

    db.add(optometrist)
    db.commit()
    # invalidate availability for the affected optometrist
    invalidate_admin_availability(
        redis_client,
        optometrist_id=optometrist.id,
    )
    db.refresh(optometrist)

    return optometrist


@router.get("", response_model=list[OptometristRead])
# lists all optometrists records.
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
    dependencies=[Depends(get_current_admin)],
)
# handles the assign optometrist to clinic workflow.
def assign_optometrist_to_clinic(
    optometrist_id: int,
    payload: OptometristClinicCreate,
    db: DbSession,
    redis_client: RedisClient,
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

    if not clinic.is_active:
        raise HTTPException(
            status_code=409,
            detail="Cannot assign optometrist to an inactive clinic",
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
    # invalidate availability for the affected optometrist
    invalidate_admin_availability(
        redis_client,
        optometrist_id=optometrist_id,
    )
    return assignment


@router.patch(
    "/{optometrist_id}",
    response_model=OptometristRead,
    dependencies=[Depends(get_current_admin)],
)
# updates the optometrist record.
def update_optometrist(
    optometrist_id: int,
    payload: OptometristUpdate,
    db: DbSession,
    redis_client: RedisClient,
) -> Optometrist:
    optometrist = db.get(Optometrist, optometrist_id)

    if optometrist is None:
        raise HTTPException(status_code=404, detail="Optometrist not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(optometrist, field, value)

    db.commit()
    # invalidate availability for the affected optometrist
    invalidate_admin_availability(
        redis_client,
        optometrist_id=optometrist_id,
    )
    db.refresh(optometrist)
    return optometrist


@router.delete(
    "/{optometrist_id}",
    status_code=204,
    dependencies=[Depends(get_current_admin)],
)
# deletes the optometrist record.
def delete_optometrist(
    optometrist_id: int, db: DbSession, redis_client: RedisClient
) -> Response:
    optometrist = db.get(Optometrist, optometrist_id)

    if optometrist is None:
        raise HTTPException(status_code=404, detail="Optometrist not found")

    try:
        with db.begin_nested():
            db.delete(optometrist)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Optometrist has related records; deactivate instead",
        ) from exc

    db.commit()
    # invalidate availability for the affected optometrist
    invalidate_admin_availability(
        redis_client,
        optometrist_id=optometrist_id,
    )
    return Response(status_code=204)
