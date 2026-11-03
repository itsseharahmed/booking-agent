"""LLM API tests."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from groq import Groq

from optometry.api.llm import router
from optometry.llm.groq_client import create_groq_client
from optometry.llm.service import LLMServiceError


# creates a test client without external api calls
def make_client(mock_groq: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[create_groq_client] = lambda: mock_groq
    return TestClient(app)


# checks that the chat endpoint returns a response
def test_chat_success(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setenv("GROQ_MODEL", "test-model")

    mock_groq = MagicMock(spec=Groq)
    mock_groq.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Hello, how can I help?"))
    ]

    client = make_client(mock_groq)
    response = client.post("/llm/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"response": "Hello, how can I help?"}


# checks that empty messages are rejected
def test_chat_rejects_empty_message() -> None:
    client = make_client(MagicMock())

    response = client.post("/llm/chat", json={"message": ""})

    assert response.status_code == 422


# checks that service failures return 503
def test_chat_service_unavailable(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setenv("GROQ_MODEL", "test-model")

    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = LLMServiceError(
        "Groq request failed"
    )

    client = make_client(mock_groq)
    response = client.post("/llm/chat", json={"message": "Hello"})

    # the service wraps supported groq sdk exceptions
    # this test instead raises an unexpected mock exception
    assert response.status_code == 503
