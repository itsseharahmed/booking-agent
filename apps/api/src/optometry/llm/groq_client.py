"""Groq API client configuration."""

from groq import Groq

from optometry.core.config import get_groq_api_key


# creates a configured groq client
def create_groq_client() -> Groq:
    return Groq(
        api_key=get_groq_api_key(),
        timeout=15.0,
        max_retries=2,
    )
