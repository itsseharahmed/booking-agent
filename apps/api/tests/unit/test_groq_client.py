"""Groq client configuration tests."""

from unittest.mock import patch

import pytest

from optometry.core.config import get_groq_api_key, get_groq_model
from optometry.llm.groq_client import create_groq_client


# checks that groq configuration is loaded
def test_groq_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")

    assert get_groq_api_key() == "test-groq-key"
    assert get_groq_model() == "test-model"


# checks that a missing groq api key is rejected
def test_missing_groq_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        get_groq_api_key()


# checks that the groq client uses configured settings
def test_create_groq_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    with patch("optometry.llm.groq_client.Groq") as mock_groq:
        client = create_groq_client()

    mock_groq.assert_called_once_with(
        api_key="test-groq-key",
        timeout=15.0,
        max_retries=2,
    )
    assert client is mock_groq.return_value
