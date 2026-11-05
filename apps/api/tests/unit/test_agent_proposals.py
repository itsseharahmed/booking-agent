"""Tests for extracting agent action proposals."""

from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from optometry.agent.proposals import (
    BookingProposal,
    CancellationProposal,
    extract_latest_proposal,
)


def test_extract_booking_proposal() -> None:
    start = datetime(2026, 11, 10, 15, tzinfo=UTC)

    messages = [
        HumanMessage(content="Book this appointment"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "propose_booking",
                    "args": {
                        "clinic_id": 1,
                        "optometrist_id": 2,
                        "service_id": 3,
                        "start_at": start.isoformat(),
                    },
                    "id": "call_1",
                }
            ],
        ),
        ToolMessage(
            content="Proposal created",
            name="propose_booking",
            tool_call_id="call_1",
        ),
        AIMessage(content="Please review the appointment."),
    ]

    result = extract_latest_proposal(messages)

    assert isinstance(result, BookingProposal)
    assert result.clinic_id == 1
    assert result.optometrist_id == 2
    assert result.service_id == 3
    assert result.start_at == start


def test_extract_cancellation_proposal() -> None:
    messages = [
        HumanMessage(content="Cancel appointment 42"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "propose_cancellation",
                    "args": {"appointment_id": 42},
                    "id": "call_2",
                }
            ],
        ),
        ToolMessage(
            content="Proposal created",
            name="propose_cancellation",
            tool_call_id="call_2",
        ),
        AIMessage(content="Please review the cancellation."),
    ]

    result = extract_latest_proposal(messages)

    assert isinstance(result, CancellationProposal)
    assert result.appointment_id == 42


def test_failed_tool_call_does_not_produce_proposal() -> None:
    messages = [
        HumanMessage(content="Cancel appointment"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "propose_cancellation",
                    "args": {"appointment_id": 42},
                    "id": "call_3",
                }
            ],
        ),
        ToolMessage(
            content="Tool failed",
            name="propose_cancellation",
            tool_call_id="call_3",
            status="error",
        ),
    ]

    assert extract_latest_proposal(messages) is None


def test_previous_turn_proposal_is_not_reused() -> None:
    messages = [
        HumanMessage(content="Cancel appointment 42"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "propose_cancellation",
                    "args": {"appointment_id": 42},
                    "id": "call_4",
                }
            ],
        ),
        ToolMessage(
            content="Proposal created",
            name="propose_cancellation",
            tool_call_id="call_4",
        ),
        AIMessage(content="Please confirm."),
        HumanMessage(content="Actually, never mind."),
        AIMessage(content="Understood."),
    ]

    assert extract_latest_proposal(messages) is None


def test_multiple_proposals_are_rejected() -> None:
    messages = [
        HumanMessage(content="Cancel two appointments"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "propose_cancellation",
                    "args": {"appointment_id": 42},
                    "id": "call_5",
                },
                {
                    "name": "propose_cancellation",
                    "args": {"appointment_id": 43},
                    "id": "call_6",
                },
            ],
        ),
        ToolMessage(
            content="First proposal",
            name="propose_cancellation",
            tool_call_id="call_5",
        ),
        ToolMessage(
            content="Second proposal",
            name="propose_cancellation",
            tool_call_id="call_6",
        ),
    ]

    assert extract_latest_proposal(messages) is None
