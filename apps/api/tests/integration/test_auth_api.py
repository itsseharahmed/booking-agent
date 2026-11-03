"""Patient registration and login integration tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from optometry.api.auth import router as auth_router
from optometry.db.models.patient import Patient
from optometry.db.session import get_db


# creates the shared test fixture.
@pytest.fixture
# builds the test client used by the test.
def client(test_session, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-only-secret-not-for-production",
    )

    # creates the api application.
    app = FastAPI()
    app.include_router(auth_router)

    # overrides a dependency during the test.
    def override_db():
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client


# handles the registration payload workflow.
def registration_payload(email="patient@example.com"):
    return {
        "first_name": "Test",
        "last_name": "Patient",
        "email": email,
        "password": "secure-password-123",
    }


# checks that register patient works as expected.
def test_register_patient(client):
    response = client.post(
        "/auth/register",
        json=registration_payload(),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["email"] == "patient@example.com"
    assert "password_hash" not in result
    assert "password" not in result


# checks that duplicate email rejected works as expected.
def test_duplicate_email_rejected(client):
    first = client.post(
        "/auth/register",
        json=registration_payload("Patient@Example.com"),
    )
    second = client.post(
        "/auth/register",
        json=registration_payload("patient@example.com"),
    )

    assert first.status_code == 201
    assert second.status_code == 409


# checks that login returns token works as expected.
def test_login_returns_token(client):
    client.post(
        "/auth/register",
        json=registration_payload(),
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "secure-password-123",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


# checks that invalid password rejected works as expected.
def test_invalid_password_rejected(client):
    client.post(
        "/auth/register",
        json=registration_payload(),
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


# checks that unknown email rejected works as expected.
def test_unknown_email_rejected(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "missing@example.com",
            "password": "secure-password-123",
        },
    )

    assert response.status_code == 401


# checks that short password rejected works as expected.
def test_short_password_rejected(client):
    payload = registration_payload()
    payload["password"] = "short"

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422


# checks that inactive patient cannot login works as expected.
def test_inactive_patient_cannot_login(client, test_session):
    created = client.post(
        "/auth/register",
        json=registration_payload(),
    )
    assert created.status_code == 201

    patient = test_session.get(
        Patient,
        created.json()["id"],
    )
    assert patient is not None

    patient.is_active = False
    test_session.flush()

    response = client.post(
        "/auth/login",
        json={
            "email": "patient@example.com",
            "password": "secure-password-123",
        },
    )

    assert response.status_code == 401
