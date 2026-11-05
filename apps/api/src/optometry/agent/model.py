"""Groq chat model for the booking agent."""

from langchain_groq import ChatGroq
from pydantic import SecretStr

from optometry.core.config import get_groq_api_key, get_groq_model


def create_agent_model() -> ChatGroq:
    return ChatGroq(
        model=get_groq_model(),
        api_key=SecretStr(get_groq_api_key()),
        temperature=0.2,
        timeout=15,
        max_retries=2,
    )
