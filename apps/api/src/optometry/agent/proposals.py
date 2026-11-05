"""Extract structured proposals from LangGraph messages."""

from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError


class BookingProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["book"] = "book"
    clinic_id: int = Field(gt=0)
    optometrist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: AwareDatetime
    requires_confirmation: Literal[True] = True


class CancellationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["cancel"] = "cancel"
    appointment_id: int = Field(gt=0)
    requires_confirmation: Literal[True] = True


ActionProposal = BookingProposal | CancellationProposal


# extracts only successful proposals from the latest patient turn
def extract_latest_proposal(
    messages: list[AnyMessage],
) -> ActionProposal | None:
    latest_turn: list[AnyMessage] = []

    for message in messages:
        if isinstance(message, HumanMessage):
            latest_turn = []

        latest_turn.append(message)

    successful_calls = {
        message.tool_call_id
        for message in latest_turn
        if isinstance(message, ToolMessage) and message.status == "success"
    }

    proposals: list[ActionProposal] = []
    proposal: ActionProposal

    for message in latest_turn:
        if not isinstance(message, AIMessage):
            continue

        for call in message.tool_calls:
            if call["id"] not in successful_calls:
                continue

            try:
                if call["name"] == "propose_booking":
                    proposal = BookingProposal.model_validate(
                        {**call["args"], "action": "book"}
                    )
                    proposals.append(proposal)

                elif call["name"] == "propose_cancellation":
                    proposal = CancellationProposal.model_validate(
                        {**call["args"], "action": "cancel"}
                    )
                    proposals.append(proposal)

            except (ValidationError, TypeError, ValueError):
                continue

    # ambiguous proposals must not be offered for approval
    if len(proposals) != 1:
        return None

    return proposals[0]
