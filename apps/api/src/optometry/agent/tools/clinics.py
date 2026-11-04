"""LangChain tools for clinic lookup."""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from optometry.api.clinics import list_clinics as fetch_clinics
from optometry.db.session import SessionLocal


# retrieves active clinics using the existing backend
def fetch_active_clinics(db: Session) -> list[dict[str, Any]]:
    clinics = fetch_clinics(db=db, active_only=True)

    return [
        {
            "id": clinic.id,
            "name": clinic.name,
            "address_line1": clinic.address_line1,
            "city": clinic.city,
            "province": clinic.province,
            "postal_code": clinic.postal_code,
        }
        for clinic in clinics
    ]


# exposes active clinics to the booking agent
@tool
def list_active_clinics() -> list[dict[str, Any]]:
    """List active optometry clinics and their locations."""
    with SessionLocal() as db:
        return fetch_active_clinics(db)
