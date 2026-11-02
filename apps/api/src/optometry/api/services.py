"""Appointment service catalog API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.auth.admin_dependencies import get_current_admin
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.session import get_db
from optometry.schemas.appointment_service import (
    AppointmentServiceCreate,
    AppointmentServiceRead,
    AppointmentServiceUpdate,
)

router = APIRouter(prefix="/services", tags=["Services"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=AppointmentServiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create_service(
    payload: AppointmentServiceCreate,
    db: DbSession,
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

    db.refresh(service)
    return service


@router.get("", response_model=list[AppointmentServiceRead])
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
def update_service(
    service_id: int,
    payload: AppointmentServiceUpdate,
    db: DbSession,
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

    db.refresh(service)
    return service


@router.delete(
    "/{service_id}",
    status_code=204,
    dependencies=[Depends(get_current_admin)],
)
def delete_service(
    service_id: int,
    db: DbSession,
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

    return Response(status_code=204)
