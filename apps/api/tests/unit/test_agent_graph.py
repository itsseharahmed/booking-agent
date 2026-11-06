"""Tests for read-only LangGraph orchestration."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from optometry.agent.graph import build_read_only_graph


# checks the graph responds without requiring tools
def test_graph_direct_response() -> None:
    model = MagicMock()
    bound_model = MagicMock()

    model.bind_tools.return_value = bound_model
    bound_model.invoke.return_value = AIMessage(
        content="I can help you find an optometry appointment."
    )

    graph = build_read_only_graph(model)

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content="Hello"),
            ]
        }
    )

    assert result["messages"][-1].content == (
        "I can help you find an optometry appointment."
    )

    registered_tools = model.bind_tools.call_args.args[0]

    assert len(registered_tools) == 7
    assert "book_appointment" not in {tool.name for tool in registered_tools}
    assert "cancel_appointment" not in {tool.name for tool in registered_tools}


# checks the graph invokes a read-only tool
def test_graph_tool_execution() -> None:
    model = MagicMock()
    bound_model = MagicMock()
    model.bind_tools.return_value = bound_model

    bound_model.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "list_active_clinics",
                    "args": {},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="I found an active clinic."),
    ]

    with (
        patch("optometry.agent.tools.clinics.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.clinics.fetch_active_clinics",
            return_value=[{"id": 1, "name": "Example Clinic"}],
        ),
    ):
        graph = build_read_only_graph(model)

        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(content="Find clinics"),
                ]
            }
        )

    assert result["messages"][-1].content == ("I found an active clinic.")

    assert any(
        isinstance(message, ToolMessage) and message.name == "list_active_clinics"
        for message in result["messages"]
    )

    mock_session.assert_called_once()


# checks empty model responses are retried
def test_graph_retries_empty_response() -> None:
    model = MagicMock()
    bound_model = MagicMock()

    model.bind_tools.return_value = bound_model

    bound_model.invoke.side_effect = [
        AIMessage(content=""),
        AIMessage(content="Available appointments found."),
    ]

    graph = build_read_only_graph(model)

    result = graph.invoke({"messages": [HumanMessage(content="Check November 7")]})

    assert result["messages"][-1].content == ("Available appointments found.")
    assert bound_model.invoke.call_count == 2

    # checks persistent empty responses produce a useful message


def test_graph_handles_repeated_empty_responses() -> None:
    model = MagicMock()
    bound_model = MagicMock()

    model.bind_tools.return_value = bound_model
    bound_model.invoke.return_value = AIMessage(content="")

    graph = build_read_only_graph(model)

    result = graph.invoke({"messages": [HumanMessage(content="Find appointments")]})

    assert "couldn't complete" in result["messages"][-1].content
    assert bound_model.invoke.call_count == 2


# checks clinic knowledge is available to the model
def test_graph_registers_clinic_knowledge_tool() -> None:
    model = MagicMock()
    bound_model = MagicMock()

    model.bind_tools.return_value = bound_model
    bound_model.invoke.return_value = AIMessage(
        content="I can check the clinic's insurance information."
    )

    graph = build_read_only_graph(model)

    result = graph.invoke(
        {"messages": [HumanMessage(content="Does test clinic accept Sun Life?")]}
    )

    registered_tools = model.bind_tools.call_args.args[0]

    assert "get_clinic_knowledge" in {
        registered_tool.name for registered_tool in registered_tools
    }

    assert result["messages"][-1].content == (
        "I can check the clinic's insurance information."
    )


# checks LangGraph executes a clinic knowledge tool call
def test_graph_executes_clinic_knowledge_tool(
    monkeypatch,
) -> None:
    from optometry.agent.tools.clinic_knowledge import (
        get_clinic_knowledge,
    )

    monkeypatch.setattr(
        get_clinic_knowledge,
        "func",
        lambda clinic_id: {
            "clinic_id": clinic_id,
            "name": "Test Clinic",
            "insurance_info": "Sun Life accepted",
        },
    )

    model = MagicMock()
    bound_model = MagicMock()
    model.bind_tools.return_value = bound_model

    bound_model.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_clinic_knowledge",
                    "args": {"clinic_id": 1},
                    "id": "clinic-knowledge-call",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Test Clinic accepts Sun Life insurance."),
    ]

    graph = build_read_only_graph(model)

    result = graph.invoke(
        {"messages": [HumanMessage(content="Does test clinic accept Sun Life?")]}
    )

    assert result["messages"][-1].content == ("Test Clinic accepts Sun Life insurance.")
    assert bound_model.invoke.call_count == 2
