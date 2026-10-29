"""API endpoints for weekly working schedules."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db
from optometry.schemas.working_schedule import (
    WorkingScheduleCreate,
    WorkingScheduleRead,
    WorkingScheduleUpdate,
)

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post(
    "",
    response_model=WorkingScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: WorkingScheduleCreate,
    db: DbSession,
) -> WorkingSchedule:
    """Create a weekly shift at an assigned clinic."""

    assignment = db.get(
        OptometristClinic,
        (payload.optometrist_id, payload.clinic_id),
    )

    if assignment is None:
        raise HTTPException(
            status_code=422,
            detail="Optometrist is not assigned to this clinic",
        )

    schedule = WorkingSchedule(**payload.model_dump())

    db.add(schedule)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Schedule conflicts with an existing shift",
        ) from exc

    db.refresh(schedule)

    return schedule


@router.get("", response_model=list[WorkingScheduleRead])
def list_schedules(
    db: DbSession,
    optometrist_id: int | None = None,
    clinic_id: int | None = None,
    active_only: bool = False,
) -> list[WorkingSchedule]:
    """List weekly shifts, optionally filtered."""

    query = select(WorkingSchedule)

    if optometrist_id is not None:
        query = query.where(WorkingSchedule.optometrist_id == optometrist_id)

    if clinic_id is not None:
        query = query.where(WorkingSchedule.clinic_id == clinic_id)

    if active_only:
        query = query.where(WorkingSchedule.is_active.is_(True))

    query = query.order_by(
        WorkingSchedule.day_of_week,
        WorkingSchedule.start_time,
        WorkingSchedule.id,
    )

    return list(db.scalars(query).all())


@router.patch(
    "/{schedule_id}",
    response_model=WorkingScheduleRead,
)
def update_schedule(
    schedule_id: int,
    payload: WorkingScheduleUpdate,
    db: DbSession,
) -> WorkingSchedule:
    """Update a shift while preserving scheduling constraints."""

    schedule = db.get(WorkingSchedule, schedule_id)

    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail="Schedule not found",
        )

    changes = payload.model_dump(exclude_unset=True)

    new_clinic_id = changes.get("clinic_id", schedule.clinic_id)
    new_start = changes.get("start_time", schedule.start_time)
    new_end = changes.get("end_time", schedule.end_time)

    if new_start >= new_end:
        raise HTTPException(
            status_code=422,
            detail="End time must be after start time",
        )

    if new_clinic_id != schedule.clinic_id:
        assignment = db.get(
            OptometristClinic,
            (schedule.optometrist_id, new_clinic_id),
        )

        if assignment is None:
            raise HTTPException(
                status_code=422,
                detail="Optometrist is not assigned to this clinic",
            )

    for field_name, value in changes.items():
        setattr(schedule, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Schedule conflicts with an existing shift",
        ) from exc

    db.refresh(schedule)
    return schedule
