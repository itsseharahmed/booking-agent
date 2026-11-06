"""LangChain tool for clinic knowledge retrieval."""

from typing import Annotated, Any

from langchain_core.tools import tool
from pydantic import Field

from optometry.agent.clinic_knowledge import fetch_clinic_knowledge
from optometry.db.session import SessionLocal


@tool
def get_clinic_knowledge(
    clinic_id: Annotated[
        int,
        Field(gt=0, description="ID of the selected clinic"),
    ],
) -> dict[str, Any]:
    """Get insurance, parking, accessibility, and policy details for a clinic."""
    with SessionLocal() as db:
        result = fetch_clinic_knowledge(db, clinic_id=clinic_id)

    if result is None:
        return {
            "error": "Clinic not found or inactive",
        }

    return result
