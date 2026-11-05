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

    assert len(registered_tools) == 6
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
