"""Authenticated LangGraph chat API."""

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from optometry.agent.conversations import run_conversation
from optometry.agent.graph import build_read_only_graph
from optometry.agent.model import create_agent_model
from optometry.agent.proposals import ActionProposal
from optometry.auth.dependencies import get_current_patient
from optometry.db.models.patient import Patient
from optometry.db.session import get_db

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)

DbSession = Annotated[Session, Depends(get_db)]
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class AgentChatResponse(BaseModel):
    conversation_id: UUID
    response: str
    proposal: ActionProposal | None = None


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    payload: AgentChatRequest,
    db: DbSession,
    patient: CurrentPatient,
) -> AgentChatResponse:
    conversation_id = payload.conversation_id or uuid4()

    try:
        graph = build_read_only_graph(create_agent_model())

        response, proposal = run_conversation(
            db=db,
            graph=graph,
            patient_id=patient.id,
            conversation_id=conversation_id,
            message=payload.message,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()
        logger.exception("Agent chat request failed")
        raise HTTPException(
            status_code=503,
            detail="Agent temporarily unavailable",
        ) from exc

    return AgentChatResponse(
        conversation_id=conversation_id, response=response, proposal=proposal
    )
