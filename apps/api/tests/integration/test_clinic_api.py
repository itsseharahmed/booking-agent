"""Integration tests for the clinic API."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.session import get_db
from optometry.main import app


@pytest.fixture
def client(test_session: Session) -> Generator[TestClient, None, None]:
    """Use the isolated test database for API requests."""

    def override_get_db() -> Generator[Session, None, None]:
        yield test_session

    # Prevent API requests from accessing the development database.
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_create_clinic(client: TestClient) -> None:
    """POST /clinics should create a clinic."""
    response = client.post(
        "/clinics",
        json={
            "name": "Downtown Vision Clinic",
            "address_line1": "123 Main Street",
            "city": "Toronto",
            "province": "Ontario",
            "postal_code": "M5V 2T6",
            "country": "CA",
            "timezone": "America/Toronto",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Downtown Vision Clinic"
    assert data["is_active"] is True


def test_list_clinics(client: TestClient) -> None:
    """GET /clinics should return a list."""
    response = client.get("/clinics")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_unknown_clinic(client: TestClient) -> None:
    """An existing route should return 404 for an unknown clinic."""
    response = client.get("/clinics/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Clinic not found"}


def test_get_existing_clinic(client: TestClient) -> None:
    """GET /clinics/{id} should return an existing clinic."""

    clinic_data = {
        "name": "Midtown Vision Clinic",
        "address_line1": "789 Yonge Street",
        "city": "Toronto",
        "province": "Ontario",
        "postal_code": "M4W 2G8",
        "country": "CA",
        "timezone": "America/Toronto",
    }

    # Create a clinic using the API.
    create_response = client.post("/clinics", json=clinic_data)

    assert create_response.status_code == 201

    clinic_id = create_response.json()["id"]

    # Retrieve the clinic using its generated ID.
    response = client.get(f"/clinics/{clinic_id}")

    assert response.status_code == 200
    assert response.json()["id"] == clinic_id
    assert response.json()["name"] == "Midtown Vision Clinic"
    assert response.json()["city"] == "Toronto"


def test_create_clinic_missing_name(client: TestClient) -> None:
    """Creating a clinic without a name should fail validation."""

    response = client.post(
        "/clinics",
        json={
            "address_line1": "123 Main Street",
            "city": "Toronto",
            "province": "Ontario",
            "postal_code": "M5V 2T6",
        },
    )

    assert response.status_code == 422


def test_create_clinic_invalid_timezone(client: TestClient) -> None:
    """Creating a clinic with an invalid timezone should fail."""

    response = client.post(
        "/clinics",
        json={
            "name": "Invalid Timezone Clinic",
            "address_line1": "123 Main Street",
            "city": "Toronto",
            "province": "Ontario",
            "postal_code": "M5V 2T6",
            "timezone": "Invalid/Timezone",
        },
    )

    assert response.status_code == 422


def test_list_multiple_clinics(client: TestClient) -> None:
    """GET /clinics should return multiple clinics."""

    clinic_names = [
        "Eastside Vision Clinic",
        "Westside Vision Clinic",
    ]

    for name in clinic_names:
        response = client.post(
            "/clinics",
            json={
                "name": name,
                "address_line1": "123 Main Street",
                "city": "Toronto",
                "province": "Ontario",
                "postal_code": "M5V 2T6",
                "country": "CA",
                "timezone": "America/Toronto",
            },
        )
        assert response.status_code == 201

    response = client.get("/clinics")

    assert response.status_code == 200

    returned_names = {clinic["name"] for clinic in response.json()}

    assert set(clinic_names).issubset(returned_names)


def test_list_only_active_clinics(
    client: TestClient,
    test_session: Session,
) -> None:
    """GET /clinics?active_only=true should exclude inactive clinics."""

    active_clinic = Clinic(
        name="Active Vision Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        is_active=True,
    )

    inactive_clinic = Clinic(
        name="Inactive Vision Clinic",
        address_line1="456 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        is_active=False,
    )

    test_session.add_all([active_clinic, inactive_clinic])
    test_session.commit()

    response = client.get("/clinics?active_only=true")

    assert response.status_code == 200

    returned_names = {clinic["name"] for clinic in response.json()}

    assert "Active Vision Clinic" in returned_names
    assert "Inactive Vision Clinic" not in returned_names


def test_create_clinic_whitespace_only_name(client: TestClient) -> None:
    """Reject clinic names containing only whitespace."""

    response = client.post(
        "/clinics",
        json={
            "name": "   ",
            "address_line1": "123 Main Street",
            "city": "Toronto",
            "province": "Ontario",
            "postal_code": "M5V 2T6",
            "country": "CA",
            "timezone": "America/Toronto",
        },
    )

    assert response.status_code == 422
