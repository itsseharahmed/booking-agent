"""Integration tests for administrator authentication."""

from collections.abc import Iterator

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.api.admin_auth import router
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    hash_password,
)
from optometry.db.models.admin import Admin
from optometry.db.session import get_db


@pytest.fixture
def client(test_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)

    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin(test_session: Session) -> Admin:
    record = Admin(
        email="admin@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )
    test_session.add(record)
    test_session.flush()
    return record


def test_admin_login_success(
    client: TestClient,
    admin: Admin,
) -> None:
    response = client.post(
        "/admin/auth/login",
        json={
            "email": "admin@example.com",
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["token_type"] == "bearer"

    claims = jwt.decode(
        body["access_token"],
        get_jwt_secret_key(),
        algorithms=[JWT_ALGORITHM],
    )

    assert claims["sub"] == str(admin.id)
    assert claims["role"] == "admin"
    assert claims["type"] == "access"


def test_admin_login_wrong_password(
    client: TestClient,
    admin: Admin,
) -> None:
    response = client.post(
        "/admin/auth/login",
        json={
            "email": admin.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_admin_login_unknown_email(
    client: TestClient,
) -> None:
    response = client.post(
        "/admin/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 401


def test_inactive_admin_cannot_login(
    client: TestClient,
    admin: Admin,
    test_session: Session,
) -> None:
    admin.is_active = False
    test_session.flush()

    response = client.post(
        "/admin/auth/login",
        json={
            "email": admin.email,
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 401


def test_patient_token_has_no_admin_role() -> None:
    token = create_access_token(
        patient_id=123,
        secret_key=get_jwt_secret_key(),
    )

    claims = jwt.decode(
        token,
        get_jwt_secret_key(),
        algorithms=[JWT_ALGORITHM],
    )

    assert claims.get("role") != "admin"
