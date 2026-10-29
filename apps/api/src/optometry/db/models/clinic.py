"""SQLAlchemy model for optometry clinic locations."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


class Clinic(Base):
    """Represent a physical clinic where appointments can be booked."""

    __tablename__ = "clinics"
    __table_args__ = (
        CheckConstraint(
            "appointment_price >= 0",
            name="ck_clinics_nonnegative_appointment_price",
        ),
        CheckConstraint(
            "appointment_price >= 0",
            name="ck_clinics_nonnegative_appointment_price",
        ),
    )
    # Unique identifier for each clinic.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Clinic identity and address.
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CA")

    # Contact details and local scheduling timezone.
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Toronto"
    )

    # Inactive clinics remain in the database but cannot accept new bookings.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Database-managed timestamps.
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
    appointment_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        server_default="0.00",
    )
