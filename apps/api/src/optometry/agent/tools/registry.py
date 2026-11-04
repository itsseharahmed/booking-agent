"""LangChain tool registry."""

from langchain_core.tools import BaseTool

from optometry.agent.tools.availability import check_appointment_availability
from optometry.agent.tools.clinics import list_active_clinics
from optometry.agent.tools.optometrists import list_active_optometrists
from optometry.agent.tools.services import list_active_services


# registers read-only tools available to the agent
def get_read_only_tools() -> list[BaseTool]:
    return [
        list_active_clinics,
        list_active_optometrists,
        list_active_services,
        check_appointment_availability,
    ]
