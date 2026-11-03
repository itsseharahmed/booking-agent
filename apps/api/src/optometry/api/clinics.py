# API endpoints for managing optometry clinic locations.

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
from optometry.db.session import get_db
from optometry.schemas.clinic import (
    ClinicAppointmentPriceUpdate,
    ClinicCreate,
    ClinicRead,
    ClinicUpdate,
)

# router for this api module.
router = APIRouter(prefix="/clinics", tags=["Clinics"])

# fastAPI injects a database session into each endpoint.
DatabaseSession = Annotated[Session, Depends(get_db)]

# provides redis for administrative cache invalidation
RedisClient = Annotated[Redis, Depends(create_redis_client)]


@router.post(
    "",
    response_model=ClinicRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
# creates a new clinic.
def create_clinic(
    clinic_data: ClinicCreate, db: DatabaseSession, redis_client: RedisClient
) -> Clinic:
    """Create a clinic and persist it to PostgreSQL."""
    clinic = Clinic(**clinic_data.model_dump())

    db.add(clinic)
    db.commit()
    # invalidate availability after the clinic change is committed
    invalidate_admin_availability(
        redis_client,
        clinic_id=clinic.id,
    )
    db.refresh(clinic)

    return clinic


@router.get("", response_model=list[ClinicRead])
# lists all clinics records.
def list_clinics(
    db: DatabaseSession,
    active_only: bool = False,
) -> list[Clinic]:
    """Return all clinics, optionally filtering for active locations."""

    statement = select(Clinic)

    # exclude inactive clinics when requested.
    if active_only:
        statement = statement.where(Clinic.is_active.is_(True))

    # keep results ordered consistently by clinic ID.
    statement = statement.order_by(Clinic.id)

    return list(db.scalars(statement).all())


@router.get("/{clinic_id}", response_model=ClinicRead)
# loads the clinic record.
def get_clinic(clinic_id: int, db: DatabaseSession) -> Clinic:
    """Retrieve a clinic by ID or return a 404 response."""
    clinic = db.get(Clinic, clinic_id)

    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found",
        )

    return clinic


@router.patch(
    "/{clinic_id}/appointment-price",
    response_model=ClinicRead,
    dependencies=[Depends(get_current_admin)],
)
# updates the clinic appointment price record.
def update_clinic_appointment_price(
    clinic_id: int,
    payload: ClinicAppointmentPriceUpdate,
    db: Annotated[Session, Depends(get_db)],
    redis_client: RedisClient,
) -> Clinic:
    """Update the standard price for every appointment at a clinic."""

    clinic = db.get(Clinic, clinic_id)

    if clinic is None:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found",
        )

    clinic.appointment_price = payload.appointment_price
    db.commit()
    # invalidate availability after the clinic change is committed
    invalidate_admin_availability(
        redis_client,
        clinic_id=clinic_id,
    )
    db.refresh(clinic)

    return clinic


@router.patch(
    "/{clinic_id}",
    response_model=ClinicRead,
    dependencies=[Depends(get_current_admin)],
)
# updates the clinic record.
def update_clinic(
    clinic_id: int,
    payload: ClinicUpdate,
    db: DatabaseSession,
    redis_client: RedisClient,
) -> Clinic:
    clinic = db.get(Clinic, clinic_id)

    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(clinic, field, value)

    db.commit()
    # invalidate availability after the clinic change is committed
    invalidate_admin_availability(
        redis_client,
        clinic_id=clinic_id,
    )
    db.refresh(clinic)
    return clinic


@router.delete(
    "/{clinic_id}",
    status_code=204,
    dependencies=[Depends(get_current_admin)],
)
# deletes the clinic record.
def delete_clinic(
    clinic_id: int, db: DatabaseSession, redis_client: RedisClient
) -> Response:
    clinic = db.get(Clinic, clinic_id)

    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")

    try:
        with db.begin_nested():
            db.delete(clinic)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Clinic has related records; deactivate it instead",
        ) from exc

    db.commit()
    # invalidate availability after the clinic change is committed
    invalidate_admin_availability(
        redis_client,
        clinic_id=clinic_id,
    )
    return Response(status_code=204)
