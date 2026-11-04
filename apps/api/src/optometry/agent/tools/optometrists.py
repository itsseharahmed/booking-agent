"""LangChain tools for optometrist lookup."""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from optometry.api.optometrists import list_optometrists as fetch_optometrists
from optometry.db.session import SessionLocal


# retrieves active optometrists
def fetch_active_optometrists(db: Session) -> list[dict[str, Any]]:
    optometrists = fetch_optometrists(db=db)

    return [
        {
            "id": optometrist.id,
            "first_name": optometrist.first_name,
            "last_name": optometrist.last_name,
        }
        for optometrist in optometrists
        if optometrist.is_active
    ]


# exposes active optometrists to the booking agent
@tool
def list_active_optometrists() -> list[dict[str, Any]]:
    """List active optometrists available in the booking system."""
    with SessionLocal() as db:
        return fetch_active_optometrists(db)
