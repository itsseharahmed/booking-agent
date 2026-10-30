"""Password hashing and JWT tests."""

from datetime import UTC, datetime, timedelta

import jwt

from optometry.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    hash_password,
    verify_password,
)

TEST_SECRET = "test-only-secret-not-for-production"


def test_password_is_hashed() -> None:
    password = "a-secure-test-password"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_rejected() -> None:
    hashed = hash_password("correct-password-123")

    assert not verify_password("incorrect-password", hashed)


def test_access_token_contains_patient_id() -> None:
    token = create_access_token(
        patient_id=42,
        secret_key=TEST_SECRET,
    )

    payload = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_access_token_expires() -> None:
    past = datetime.now(UTC) - timedelta(hours=2)

    token = create_access_token(
        patient_id=42,
        secret_key=TEST_SECRET,
        now=past,
    )

    try:
        jwt.decode(
            token,
            TEST_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        pass
    else:
        raise AssertionError("Expired token was accepted")
