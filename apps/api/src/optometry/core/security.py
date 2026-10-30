"""Password hashing and JWT access tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()

ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(
    *,
    patient_id: int,
    secret_key: str,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)

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
