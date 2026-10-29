"""Recurring weekly working schedules for optometrists."""

from datetime import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


class WorkingSchedule(Base):
    """Represent a recurring shift at an assigned clinic."""

    __tablename__ = "working_schedules"

    __table_args__ = (
        # A shift must belong to a valid optometrist-clinic assignment.
        ForeignKeyConstraint(
            ["optometrist_id", "clinic_id"],
            [
                "optometrist_clinics.optometrist_id",
                "optometrist_clinics.clinic_id",
            ],
        ),
        # Monday = 0, Sunday = 6.
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_working_schedules_day_of_week",
        ),
        # For now, shifts must begin and end on the same day.
        CheckConstraint(
            "start_time < end_time",
            name="ck_working_schedules_time_order",
        ),
        Index(
            "uq_working_schedules_active_clinic_day",
            "optometrist_id",
            "clinic_id",
            "day_of_week",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    optometrist_id: Mapped[int] = mapped_column(Integer, nullable=False)
    clinic_id: Mapped[int] = mapped_column(Integer, nullable=False)

    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    # Local clock times in the clinic's timezone.
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
