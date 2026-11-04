"""LangChain tools for appointment service lookup."""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from optometry.api.services import list_services as fetch_services
from optometry.db.session import SessionLocal


# retrieves active appointment services
def fetch_active_services(db: Session) -> list[dict[str, Any]]:
    services = fetch_services(db=db, active_only=True)

    return [
        {
            "id": service.id,
            "name": service.name,
        }
        for service in services
    ]


# exposes active services to the booking agent
@tool
def list_active_services() -> list[dict[str, Any]]:
    """List active appointment services offered by the clinics."""
    with SessionLocal() as db:
        return fetch_active_services(db)
