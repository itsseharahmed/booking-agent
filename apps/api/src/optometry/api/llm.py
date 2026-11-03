"""Groq LLM API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from groq import Groq
from pydantic import BaseModel, Field

from optometry.core.config import get_groq_model
from optometry.llm.groq_client import create_groq_client
from optometry.llm.service import LLMServiceError, generate_response

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class LLMResponse(BaseModel):
    response: str


# handles natural language messages
@router.post("/chat", response_model=LLMResponse)
def chat(
    payload: LLMRequest,
    client: Annotated[Groq, Depends(create_groq_client)],
) -> LLMResponse:
    try:
        response = generate_response(
            client=client,
            model=get_groq_model(),
            message=payload.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail="LLM service temporarily unavailable",
        ) from exc

    return LLMResponse(response=response)
