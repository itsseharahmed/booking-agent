# Appointment service catalog API.

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.auth.admin_dependencies import get_current_admin
from optometry.cache.admin_invalidation import invalidate_admin_availability
from optometry.cache.redis_client import create_redis_client
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.session import get_db
from optometry.schemas.appointment_service import (
    AppointmentServiceCreate,
    AppointmentServiceRead,
    AppointmentServiceUpdate,
)

# router for this api module.
router = APIRouter(prefix="/services", tags=["Services"])

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]

# provides redis for administrative cache invalidation
RedisClient = Annotated[Redis, Depends(create_redis_client)]


@router.post(
    "",
    response_model=AppointmentServiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
# creates a new service.
def create_service(
    payload: AppointmentServiceCreate, db: DbSession, redis_client: RedisClient
) -> AppointmentService:
    service = AppointmentService(**payload.model_dump())
    db.add(service)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Service name already exists",
        ) from exc

    # invalidate availability for the affected service
    invalidate_admin_availability(
        redis_client,
        service_id=service.id,
    )
    db.refresh(service)
    return service


@router.get("", response_model=list[AppointmentServiceRead])
# lists all services records.
def list_services(
    db: DbSession,
    active_only: bool = False,
) -> list[AppointmentService]:
    query = select(AppointmentService)

    if active_only:
        query = query.where(AppointmentService.is_active.is_(True))

    query = query.order_by(AppointmentService.name, AppointmentService.id)
    return list(db.scalars(query).all())


@router.get("/{service_id}", response_model=AppointmentServiceRead)
# loads the service record.
def get_service(
    service_id: int,
    db: DbSession,
) -> AppointmentService:
    service = db.get(AppointmentService, service_id)

    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@router.patch(
    "/{service_id}",
    response_model=AppointmentServiceRead,
    dependencies=[Depends(get_current_admin)],
)
# updates the service record.
def update_service(
    service_id: int,
    payload: AppointmentServiceUpdate,
    db: DbSession,
    redis_client: RedisClient,
) -> AppointmentService:
    service = db.get(AppointmentService, service_id)

    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field_name, value)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Service name already exists",
        ) from exc

    # invalidate availability for the affected service
    invalidate_admin_availability(
        redis_client,
        service_id=service.id,
    )
    db.refresh(service)
    return service


@router.delete(
    "/{service_id}",
    status_code=204,
    dependencies=[Depends(get_current_admin)],
)
# deletes the service record.
def delete_service(
    service_id: int, db: DbSession, redis_client: RedisClient
) -> Response:
    service = db.get(AppointmentService, service_id)

    if service is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment service not found",
        )

    try:
        with db.begin_nested():
            db.delete(service)
            db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Service has related appointments; deactivate it instead",
        ) from exc

    db.commit()
    # invalidate availability for the affected service
    invalidate_admin_availability(
        redis_client,
        service_id=service.id,
    )
    return Response(status_code=204)
