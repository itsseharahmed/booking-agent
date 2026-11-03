"""Password hashing and JWT access tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

# build a strong password hasher once so all auth checks use the same settings.
password_hasher = PasswordHash.recommended()

# how long the access token stays valid before expiring.
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# jwt signing method used for all generated tokens.
JWT_ALGORITHM = "HS256"


# hashes a plain-text password before saving it in the database.
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


# checks whether a submitted password matches the stored hash.
def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


# creates a JWT for a patient after successful login.
def create_access_token(
    *,
    patient_id: int,
    secret_key: str,
    now: datetime | None = None,
) -> str:
    # use the current UTC time unless a test or caller supplies a specific timestamp.
    issued_at = now or datetime.now(UTC)

    # store the user identity and expiry time in the token payload.
    payload: dict[str, Any] = {
        "sub": str(patient_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=JWT_ALGORITHM,
    )


# creates a JWT for an admin with an extra role claim for permission checks.
def create_admin_access_token(
    *,
    admin_id: int,
    secret_key: str,
    now: datetime | None = None,
) -> str:
    # use the current UTC time unless a test or caller supplies a specific timestamp.
    issued_at = now or datetime.now(UTC)

    # include the admin id and role so downstream auth can tell who is logged in.
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
        "role": "admin",
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=JWT_ALGORITHM,
    )
