"""Tests for agent execution token hashing."""

import pytest

from optometry.agent.executions import hash_confirmation_token


def test_confirmation_token_hash_is_deterministic() -> None:
    token = "test-confirmation-token"

    first = hash_confirmation_token(token)
    second = hash_confirmation_token(token)

    assert first == second
    assert len(first) == 64
    assert token != first


def test_different_tokens_have_different_hashes() -> None:
    assert hash_confirmation_token("confirmation-one") != hash_confirmation_token(
        "confirmation-two"
    )


def test_empty_confirmation_token_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_confirmation_token("")
