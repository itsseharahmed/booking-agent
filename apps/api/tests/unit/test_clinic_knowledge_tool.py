"""Tests for the clinic knowledge LangChain tool."""

from unittest.mock import MagicMock, patch

from optometry.agent.tools.clinic_knowledge import get_clinic_knowledge


def test_tool_returns_clinic_information() -> None:
    expected = {
        "clinic_id": 1,
        "name": "Test Clinic",
        "insurance_info": "Sun Life accepted",
        "parking_info": "Free parking",
    }

    with (
        patch("optometry.agent.tools.clinic_knowledge.SessionLocal") as session_factory,
        patch(
            "optometry.agent.tools.clinic_knowledge.fetch_clinic_knowledge",
            return_value=expected,
        ) as fetch,
    ):
        session_factory.return_value.__enter__.return_value = MagicMock()

        result = get_clinic_knowledge.invoke({"clinic_id": 1})

    assert result == expected
    fetch.assert_called_once()


def test_tool_handles_missing_clinic() -> None:
    with (
        patch("optometry.agent.tools.clinic_knowledge.SessionLocal"),
        patch(
            "optometry.agent.tools.clinic_knowledge.fetch_clinic_knowledge",
            return_value=None,
        ),
    ):
        result = get_clinic_knowledge.invoke({"clinic_id": 999})

    assert result == {
        "error": "Clinic not found or inactive",
    }


def test_registry_includes_clinic_knowledge() -> None:
    from optometry.agent.tools.registry import get_read_only_tools

    tools = get_read_only_tools()

    assert len(tools) == 7
    assert "get_clinic_knowledge" in {registered_tool.name for registered_tool in tools}
