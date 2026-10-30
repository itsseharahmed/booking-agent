"""Persisted appointment bookings."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    __table_args__ = (
        ForeignKeyConstraint(
            ["optometrist_id", "clinic_id"],
            [
                "optometrist_clinics.optometrist_id",
                "optometrist_clinics.clinic_id",
            ],
            name="fk_appointments_optometrist_clinic",
        ),
        CheckConstraint(
            "end_at > start_at",
            name="ck_appointments_positive_interval",
        ),
        CheckConstraint(
            "appointment_price >= 0",
            name="ck_appointments_nonnegative_price",
        ),
        CheckConstraint(
            "status IN ('booked', 'cancelled')",
            name="ck_appointments_valid_status",
        ),
        CheckConstraint(
            "end_at - start_at = INTERVAL '20 minutes'",
            name="ck_appointments_twenty_minutes",
        ),
        CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL) "
            "OR (status = 'booked' AND cancelled_at IS NULL)",
            name="ck_appointments_cancellation_consistency",
        ),
        Index(
            "ix_appointments_clinic_start",
            "clinic_id",
            "start_at",
        ),
        Index(
            "ix_appointments_optometrist_start",
            "optometrist_id",
            "start_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id"),
        nullable=False,
    )

    optometrist_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    service_id: Mapped[int] = mapped_column(
        ForeignKey("appointment_services.id"),
        nullable=False,
    )

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="booked",
    )

    appointment_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
