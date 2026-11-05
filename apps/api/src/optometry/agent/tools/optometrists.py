"""LangChain tools for clinic-specific optometrist lookup."""

from typing import Annotated, Any

from langchain_core.tools import tool
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.session import SessionLocal


# retrieves active optometrists assigned to an active clinic
def fetch_active_optometrists(
    db: Session,
    clinic_id: int,
) -> list[dict[str, Any]]:
    if clinic_id <= 0:
        raise ValueError("A valid clinic ID is required")

    statement = (
        select(Optometrist)
        .join(
            OptometristClinic,
            OptometristClinic.optometrist_id == Optometrist.id,
        )
        .join(
            Clinic,
            Clinic.id == OptometristClinic.clinic_id,
        )
        .where(
            Clinic.id == clinic_id,
            Clinic.is_active.is_(True),
            Optometrist.is_active.is_(True),
        )
        .order_by(Optometrist.last_name, Optometrist.first_name)
    )

    optometrists = db.scalars(statement).all()

    return [
        {
            "id": optometrist.id,
            "first_name": optometrist.first_name,
            "last_name": optometrist.last_name,
        }
        for optometrist in optometrists
    ]


# exposes clinic-specific optometrists to the agent
@tool
def list_active_optometrists(
    clinic_id: Annotated[
        int,
        Field(gt=0, description="ID of the selected clinic"),
    ],
) -> list[dict[str, Any]]:
    """List active optometrists assigned to the selected active clinic."""
    with SessionLocal() as db:
        return fetch_active_optometrists(db, clinic_id)
