"""Read-only clinic knowledge retrieval."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.clinic_knowledge import ClinicKnowledge


def fetch_clinic_knowledge(
    db: Session,
    *,
    clinic_id: int,
) -> dict[str, Any] | None:
    # reject invalid clinic identifiers
    if clinic_id <= 0:
        return None

    # only return information for an active clinic
    row = db.execute(
        select(Clinic, ClinicKnowledge)
        .outerjoin(
            ClinicKnowledge,
            ClinicKnowledge.clinic_id == Clinic.id,
        )
        .where(
            Clinic.id == clinic_id,
            Clinic.is_active.is_(True),
        )
    ).one_or_none()

    if row is None:
        return None

    clinic, knowledge = row

    return {
        "clinic_id": clinic.id,
        "name": clinic.name,
        "address": {
            "address_line1": clinic.address_line1,
            "city": clinic.city,
            "province": clinic.province,
            "postal_code": clinic.postal_code,
            "country": clinic.country,
        },
        "timezone": clinic.timezone,
        "insurance_info": (knowledge.insurance_info if knowledge is not None else None),
        "parking_info": (knowledge.parking_info if knowledge is not None else None),
        "accessibility_info": (
            knowledge.accessibility_info if knowledge is not None else None
        ),
        "appointment_policy": (
            knowledge.appointment_policy if knowledge is not None else None
        ),
        "additional_info": (
            knowledge.additional_info if knowledge is not None else None
        ),
    }
