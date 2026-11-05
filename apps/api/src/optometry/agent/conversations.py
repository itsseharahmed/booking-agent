"""Persistent LangGraph conversation management."""

import re
from typing import Any
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    messages_from_dict,
    messages_to_dict,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from optometry.agent.proposals import ActionProposal, extract_latest_proposal
from optometry.db.models.agent_conversation import AgentConversation

MAX_HISTORY_MESSAGES = 40

# chat cannot finalize appointment changes
CONFIRMATION_MESSAGE = (
    "Your appointment has not been booked or cancelled. "
    "To complete the action, review the verified details and use "
    "the approval and confirmation buttons in the booking interface."
)

SUCCESS_CLAIM_PATTERN = re.compile(
    r"\b(?:"
    r"(?:appointment|booking|cancellation)\s+"
    r"(?:has been |was |is )?"
    r"(?:confirmed|booked|cancelled|canceled)"
    r"|(?:successfully\s+)?(?:booked|cancelled|canceled)\s+"
    r"(?:your|the)\s+appointment"
    r")\b",
    re.IGNORECASE,
)


def enforce_chat_write_boundary(
    *,
    patient_message: str,
    assistant_response: str,
) -> str:
    # chat confirmation does not authorize a database write
    if patient_message.strip().lower() in {
        "confirm",
        "confirmed",
        "yes confirm",
        "confirm booking",
        "confirm cancellation",
    }:
        return CONFIRMATION_MESSAGE

    # reject unsupported claims of completed actions
    if SUCCESS_CLAIM_PATTERN.search(assistant_response):
        return CONFIRMATION_MESSAGE

    return assistant_response


def run_conversation(
    *,
    db: Session,
    graph: Any,
    patient_id: int,
    conversation_id: UUID,
    message: str,
) -> tuple[str, ActionProposal | None]:
    if patient_id <= 0:
        raise ValueError("Authenticated patient required")

    if not message.strip():
        raise ValueError("Message cannot be empty")

    # create the row if this patient does not already own it
    statement = (
        insert(AgentConversation)
        .values(
            patient_id=patient_id,
            id=conversation_id,
            messages=[],
        )
        .on_conflict_do_nothing(
            index_elements=["patient_id", "id"],
        )
    )

    db.execute(statement)

    # serialize concurrent requests to the same conversation
    conversation = db.scalar(
        select(AgentConversation)
        .where(
            AgentConversation.patient_id == patient_id,
            AgentConversation.id == conversation_id,
        )
        .with_for_update()
    )

    if conversation is None:
        raise RuntimeError("Could not load conversation")

    history = messages_from_dict(conversation.messages)

    result = graph.invoke(
        {
            "messages": [
                *history,
                HumanMessage(content=message),
            ]
        },
        config={"recursion_limit": 12},
    )

    messages = result["messages"]
    proposal = extract_latest_proposal(messages)

    if not messages or not isinstance(messages[-1], AIMessage):
        raise RuntimeError("Agent did not return a final response")

    response = messages[-1].content

    if not isinstance(response, str) or not response.strip():
        raise RuntimeError("Agent returned an empty response")

    response = enforce_chat_write_boundary(
        patient_message=message,
        assistant_response=response,
    )

    # persist the corrected response, not the misleading original
    messages[-1] = AIMessage(content=response)
    # retain complete recent turns without splitting tool-call sequences
    turns: list[list[Any]] = []

    for item in messages:
        if isinstance(item, HumanMessage):
            turns.append([])
        if not turns:
            turns.append([])
        turns[-1].append(item)

    recent: list[Any] = []
    for turn in reversed(turns):
        if recent and len(recent) + len(turn) > MAX_HISTORY_MESSAGES:
            break
        recent = turn + recent

    conversation.messages = messages_to_dict(recent)
    db.commit()

    return response, proposal
