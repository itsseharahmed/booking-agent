"""Groq LLM service tests."""

from unittest.mock import MagicMock

import pytest
from groq import APIConnectionError
from httpx import Request

from optometry.llm.service import LLMServiceError, generate_response


# checks that groq returns a valid text response
def test_generate_response_success() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Available appointments can be searched."))
    ]

    response = generate_response(
        client=client,
        model="test-model",
        message="Can I book an eye exam?",
    )

    assert response == "Available appointments can be searched."
    client.chat.completions.create.assert_called_once()


# checks that empty messages are rejected
def test_generate_response_rejects_empty_message() -> None:
    client = MagicMock()

    with pytest.raises(ValueError, match="Message cannot be empty"):
        generate_response(
            client=client,
            model="test-model",
            message="   ",
        )

    client.chat.completions.create.assert_not_called()


# checks that empty groq responses are rejected
def test_generate_response_rejects_empty_response() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=None))
    ]

    with pytest.raises(LLMServiceError, match="empty response"):
        generate_response(
            client=client,
            model="test-model",
            message="Hello",
        )


# checks that groq connection failures are handled
def test_generate_response_handles_connection_error() -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = APIConnectionError(
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )

    with pytest.raises(LLMServiceError, match="Groq request failed"):
        generate_response(
            client=client,
            model="test-model",
            message="Hello",
        )
