"""Tests for the LangChain tool registry."""

from optometry.agent.tools.registry import get_read_only_tools


# checks registered tool names
def test_read_only_tool_registry() -> None:
    tools = get_read_only_tools()

    assert len(tools) == 7
    assert {tool.name for tool in tools} == {
        "list_active_clinics",
        "list_active_optometrists",
        "list_active_services",
        "check_appointment_availability",
        "propose_booking",
        "propose_cancellation",
        "get_clinic_knowledge",
    }


# checks write tools are not exposed
def test_write_tools_not_registered() -> None:
    names = {tool.name for tool in get_read_only_tools()}

    assert "book_appointment" not in names
    assert "cancel_appointment" not in names
