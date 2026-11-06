"""Clinic information used by the booking assistant."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


class ClinicKnowledge(Base):
    __tablename__ = "clinic_knowledge"

    # one information record per clinic
    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"),
        primary_key=True,
    )

    insurance_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    parking_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    accessibility_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointment_policy: Mapped[str | None] = mapped_column(Text, nullable=True)

    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
