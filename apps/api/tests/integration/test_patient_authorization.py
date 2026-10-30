"""Patient authentication and appointment ownership tests."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from optometry.api.appointments import router as appointments_router
from optometry.api.patients import router as patients_router
from optometry.core.security import create_access_token, hash_password
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.patient import Patient
from optometry.db.session import get_db

TEST_SECRET = "test-only-secret-not-for-production"


@pytest.fixture
def auth_data(test_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

    owner = Patient(
        first_name="First",
        last_name="Patient",
        email="owner@example.com",
        password_hash=hash_password("owner-password-123"),
    )
    other = Patient(
        first_name="Second",
        last_name="Patient",
        email="other@example.com",
        password_hash=hash_password("other-password-123"),
    )
    clinic = Clinic(
        name="Authorization Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
    )
    optometrist = Optometrist(
        first_name="Authorization",
        last_name="Tester",
    )
    service = AppointmentService(
        name="Authorization Test Eye Exam",
    )

    test_session.add_all([owner, other, clinic, optometrist, service])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    start = datetime.now(UTC) + timedelta(days=30)
    start = start.replace(hour=14, minute=0, second=0, microsecond=0)

    appointment = Appointment(
        patient_id=owner.id,
        clinic_id=clinic.id,
        optometrist_id=optometrist.id,
        service_id=service.id,
        start_at=start,
        end_at=start + timedelta(minutes=20),
        status="booked",
        appointment_price=clinic.appointment_price,
    )

    test_session.add(appointment)
    test_session.flush()

    return {
        "owner_id": owner.id,
        "other_id": other.id,
        "appointment_id": appointment.id,
        "clinic_id": clinic.id,
    }


@pytest.fixture
def client(test_session, auth_data):
    app = FastAPI()
    app.include_router(appointments_router)
    app.include_router(patients_router)

    def override_db():
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client


def auth_headers(patient_id, *, now=None):
    token = create_access_token(
        patient_id=patient_id,
        secret_key=TEST_SECRET,
        now=now,
    )
    return {"Authorization": f"Bearer {token}"}


def test_patient_can_read_own_profile(client, auth_data):
    response = client.get(
        "/patients/me",
        headers=auth_headers(auth_data["owner_id"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == auth_data["owner_id"]
    assert response.json()["email"] == "owner@example.com"
    assert "password_hash" not in response.json()


def test_profile_requires_authentication(client):
    response = client.get("/patients/me")

    assert response.status_code == 401


def test_booking_list_requires_authentication(client):
    response = client.get("/appointments")

    assert response.status_code == 401


def test_booking_creation_requires_authentication(client):
    response = client.post(
        "/appointments",
        json={
            "clinic_id": 1,
            "optometrist_id": 1,
            "service_id": 1,
            "start_at": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 401


def test_patient_cannot_read_another_appointment(client, auth_data):
    response = client.get(
        f"/appointments/{auth_data['appointment_id']}",
        headers=auth_headers(auth_data["other_id"]),
    )

    assert response.status_code == 404


def test_patient_cannot_cancel_another_appointment(client, auth_data):
    response = client.post(
        f"/appointments/{auth_data['appointment_id']}/cancel",
        headers=auth_headers(auth_data["other_id"]),
    )

    assert response.status_code == 404


def test_patient_list_excludes_other_appointments(client, auth_data):
    response = client.get(
        "/appointments",
        headers=auth_headers(auth_data["other_id"]),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_owner_can_read_appointment(client, auth_data):
    response = client.get(
        f"/appointments/{auth_data['appointment_id']}",
        headers=auth_headers(auth_data["owner_id"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == auth_data["appointment_id"]


def test_invalid_token_rejected(client):
    response = client.get(
        "/patients/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_expired_token_rejected(client, auth_data):
    past = datetime.now(UTC) - timedelta(hours=2)

    response = client.get(
        "/patients/me",
        headers=auth_headers(
            auth_data["owner_id"],
            now=past,
        ),
    )

    assert response.status_code == 401


def test_inactive_patient_token_rejected(client, test_session, auth_data):
    patient = test_session.get(Patient, auth_data["owner_id"])
    assert patient is not None

    patient.is_active = False
    test_session.flush()

    response = client.get(
        "/patients/me",
        headers=auth_headers(auth_data["owner_id"]),
    )

    assert response.status_code == 401


def test_token_for_nonexistent_patient_rejected(client):
    response = client.get(
        "/patients/me",
        headers=auth_headers(99999999),
    )

    assert response.status_code == 401
