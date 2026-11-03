"""Association model connecting optometrists and clinics."""
# this file contains the src / optometry / db / models / optometrist_clinic.py logic.

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


# handles the OptometristClinic workflow.
class OptometristClinic(Base):
    """Record which clinics an optometrist is assigned to."""

    __tablename__ = "optometrist_clinics"

    # composite primary key prevents duplicate assignments.
    optometrist_id: Mapped[int] = mapped_column(
        ForeignKey("optometrists.id"),
        primary_key=True,
    )

    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id"),
        primary_key=True,
    )
