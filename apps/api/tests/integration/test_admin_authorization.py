"""Integration tests for administrator authorization."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.core.config import get_jwt_secret_key
from optometry.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    create_admin_access_token,
    hash_password,
)
from optometry.db.models.admin import Admin
from optometry.db.models.patient import Patient
from optometry.db.session import get_db
from optometry.main import app


@pytest.fixture
def client(test_session: Session) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_admin_endpoint_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/clinics",
        json={},
    )

    assert response.status_code == 401


def test_patient_token_cannot_access_admin_endpoint(
    client: TestClient,
) -> None:
    token = create_access_token(
        patient_id=1,
        secret_key=get_jwt_secret_key(),
    )

    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_token_can_reach_endpoint_validation(
    client: TestClient,
    test_session: Session,
) -> None:
    admin = Admin(
        email="authorization@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )
    test_session.add(admin)
    test_session.flush()

    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )

    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Authentication succeeded; invalid clinic data is rejected.
    assert response.status_code == 422


def test_invalid_admin_token_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_admin_token_cannot_access_patient_endpoint(
    client: TestClient,
    test_session: Session,
) -> None:
    """An admin JWT must not authenticate as a patient."""

    patient = Patient(
        first_name="Test",
        last_name="Patient",
        email="patient-isolation@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )

    test_session.add(patient)
    test_session.flush()

    # Use the patient's numeric ID as the admin token subject.
    # This proves matching IDs cannot bypass role isolation.
    token = create_admin_access_token(
        admin_id=patient.id,
        secret_key=get_jwt_secret_key(),
    )

    response = client.get(
        "/patients/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_expired_admin_token_is_rejected(
    client: TestClient,
) -> None:
    """Expired administrator JWTs must return 401."""
    now = datetime.now(UTC)

    token = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "type": "access",
            "role": "admin",
        },
        get_jwt_secret_key(),
        algorithm=JWT_ALGORITHM,
    )

    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_inactive_admin_is_rejected(
    client: TestClient,
    test_session: Session,
) -> None:
    """A valid JWT cannot authenticate a disabled administrator."""
    admin = Admin(
        email="inactive-security@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=False,
    )
    test_session.add(admin)
    test_session.flush()

    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )

    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_nonexistent_admin_is_rejected(
    client: TestClient,
) -> None:
    """A validly signed JWT cannot authenticate a nonexistent admin."""
    token = create_admin_access_token(
        admin_id=2147483647,
        secret_key=get_jwt_secret_key(),
    )

    response = client.post(
        "/clinics",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# Administrative write operations that must require an admin JWT.
ADMIN_WRITE_ENDPOINTS = [
    ("POST", "/clinics"),
    ("PATCH", "/clinics/999999"),
    ("DELETE", "/clinics/999999"),
    ("PATCH", "/clinics/999999/appointment-price"),
    ("POST", "/optometrists"),
    ("PATCH", "/optometrists/999999"),
    ("DELETE", "/optometrists/999999"),
    ("POST", "/optometrists/999999/clinics"),
    ("POST", "/schedules"),
    ("PATCH", "/schedules/999999"),
    ("DELETE", "/schedules/999999"),
    ("POST", "/services"),
    ("PATCH", "/services/999999"),
    ("DELETE", "/services/999999"),
]


@pytest.mark.parametrize("method,path", ADMIN_WRITE_ENDPOINTS)
def test_admin_write_endpoint_requires_authentication(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    """Every administrative write endpoint must reject anonymous requests."""

    response = client.request(
        method,
        path,
        json={} if method in {"POST", "PATCH"} else None,
    )

    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code}, "
        f"expected 401. Response: {response.text}"
    )


@pytest.mark.parametrize("method,path", ADMIN_WRITE_ENDPOINTS)
def test_patient_cannot_access_admin_write_endpoint(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    """Patient JWTs must not grant administrative permissions."""

    token = create_access_token(
        patient_id=1,
        secret_key=get_jwt_secret_key(),
    )

    response = client.request(
        method,
        path,
        json={} if method in {"POST", "PATCH"} else None,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, (
        f"{method} {path} returned {response.status_code}, "
        f"expected 403. Response: {response.text}"
    )
