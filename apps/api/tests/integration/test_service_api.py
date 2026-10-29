"""Integration tests for the appointment service API."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.session import get_db
from optometry.main import app


@pytest.fixture
def client(test_session: Session):
    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_create_service(client: TestClient) -> None:
    response = client.post(
        "/services",
        json={
            "name": "Comprehensive Eye Exam",
            "description": "Routine eye examination",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Comprehensive Eye Exam"
    assert response.json()["is_active"] is True


def test_list_and_retrieve_services(client: TestClient) -> None:
    created = client.post(
        "/services",
        json={"name": "Contact Lens Assessment"},
    )
    service_id = created.json()["id"]

    listing = client.get("/services")
    detail = client.get(f"/services/{service_id}")

    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == service_id


def test_update_and_deactivate_service(client: TestClient) -> None:
    created = client.post(
        "/services",
        json={"name": "Follow-up Examination"},
    )
    service_id = created.json()["id"]

    response = client.patch(
        f"/services/{service_id}",
        json={
            "name": "Follow-up Eye Examination",
            "is_active": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Follow-up Eye Examination"
    assert response.json()["is_active"] is False

    active_listing = client.get("/services", params={"active_only": True})
    assert active_listing.status_code == 200
    assert active_listing.json() == []


def test_duplicate_service_rejected(client: TestClient) -> None:
    payload = {"name": "Duplicate Eye Exam"}

    assert client.post("/services", json=payload).status_code == 201

    response = client.post("/services", json=payload)
    assert response.status_code == 409


@pytest.mark.parametrize("name", ["", "   "])
def test_invalid_service_name(
    client: TestClient,
    name: str,
) -> None:
    response = client.post("/services", json={"name": name})
    assert response.status_code == 422


def test_missing_service_returns_404(client: TestClient) -> None:
    assert client.get("/services/999999").status_code == 404
    assert (
        client.patch(
            "/services/999999",
            json={"is_active": False},
        ).status_code
        == 404
    )


def test_update_clinic_appointment_price(
    client: TestClient,
    test_session: Session,
) -> None:
    clinic = Clinic(
        name="Pricing API Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )
    test_session.add(clinic)
    test_session.flush()

    response = client.patch(
        f"/clinics/{clinic.id}/appointment-price",
        json={"appointment_price": "125.00"},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["appointment_price"]) == Decimal("125.00")


@pytest.mark.parametrize("price", ["-1.00", "12.345"])
def test_invalid_clinic_price(
    client: TestClient,
    test_session: Session,
    price: str,
) -> None:
    clinic = Clinic(
        name="Invalid Price API Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )
    test_session.add(clinic)
    test_session.flush()

    response = client.patch(
        f"/clinics/{clinic.id}/appointment-price",
        json={"appointment_price": price},
    )

    assert response.status_code == 422


def test_missing_clinic_price_update(client: TestClient) -> None:
    response = client.patch(
        "/clinics/999999/appointment-price",
        json={"appointment_price": "100.00"},
    )
    assert response.status_code == 404


def test_service_names_are_normalized(client: TestClient) -> None:
    response = client.post(
        "/services",
        json={"name": "  Comprehensive   Eye   Exam  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Comprehensive Eye Exam"


def test_service_can_be_reactivated(client: TestClient) -> None:
    created = client.post(
        "/services",
        json={"name": "Reactivation Test"},
    )
    service_id = created.json()["id"]

    assert (
        client.patch(
            f"/services/{service_id}",
            json={"is_active": False},
        ).status_code
        == 200
    )

    response = client.patch(
        f"/services/{service_id}",
        json={"is_active": True},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True
