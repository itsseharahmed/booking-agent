"""Helpers for durable agent action execution."""

import hashlib


def hash_confirmation_token(token: str) -> str:
    # hash the high-entropy confirmation token before database storage
    if not token:
        raise ValueError("Confirmation token cannot be empty")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
